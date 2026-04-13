# ==================== 标准库导入 ====================
import asyncio
import atexit
import copy
import datetime
import gc
import json
import logging
import os
import signal
import sys
import threading
import time
from decimal import ROUND_DOWN, Decimal
from enum import Enum
from typing import List, Optional

# ==================== 第三方库导入 ====================
import aiofiles
import aiohttp
import akshare as ak
import baostock as bs
import pandas as pd
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from binance_common.configuration import ConfigurationRestAPI
from binance_sdk_derivatives_trading_portfolio_margin.derivatives_trading_portfolio_margin import (
    DerivativesTradingPortfolioMargin,
)
from binance_sdk_derivatives_trading_portfolio_margin.rest_api.models import (
    NewUmOrderPositionSideEnum,
    NewUmOrderSideEnum,
    NewUmOrderTypeEnum,
)
from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (
    DerivativesTradingUsdsFutures,
)
from pydantic import BaseModel
from requests.adapters import HTTPAdapter

# ==================== 类型定义 ====================


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BZ = "BZ"
    BD = "BD"
    N = "N"
    Basis = "Basis"
    DCA = "DCA"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Position(BaseModel):
    """
    持仓信息数据类 (AUTOBN/AUTOA 通用)

    字段：
        take_profit: 止盈价
        stop_loss: 止损价
        close_side: 平仓方向 (BUY/SELL)
        position_side: 持仓方向 (LONG/SHORT)
        entry_price: 开仓均价
        name: 品种名称 (AUTOBN: symbol, AUTOA: 股票名称)
        date: 开仓日期 (YYYYMMDD 格式)
        strategy: 策略标签列表 (BZ/BD/Supertrend)
        tp_count: 止盈次数 (用于加速衰减)
    """

    take_profit: float
    stop_loss: float
    close_side: OrderSide
    position_side: PositionSide
    entry_price: float
    name: str
    date: int
    strategy: List[PositionSide]
    tp_count: int = 0  # 止盈次数，每次部分止盈后+1，衰减加速系数
    oi_guard_threshold: float = 0.0  # OI保护阈值（多头开仓通过时记录，DCA时用于风控）
    close_reason: str = (
        ""  # 平仓依据（止盈/初始止损/追踪止损/移动止损/DCA多空比异常且OI不满足等）
    )


class Observation(BaseModel):
    """
    观察列表信息数据类 (AUTOBN/AUTOA 通用)

    用途：记录待观察的交易机会
    字段：
        price: 触发价格
        timestamp: 触发时间（Unix时间戳）
        side: 信号方向 (BUY/SELL)
        strategy: 策略标签列表 (LONG/SHORT/BZ/BD/Supertrend)
        name: 品种名称 (AUTOBN: symbol, AUTOA: 股票名称)
    """

    price: float
    timestamp: float
    side: OrderSide
    strategy: List[PositionSide]
    name: str


# HTTP 会话配置（可覆盖）
session = requests.Session()
session.verify = False
session.headers = {"Content-Type": "application/json"}


# ==================== 平仓记录管理 ====================
class CloseRecordManager:
    """
    全局平仓记录管理器

    功能：将AUTOBN和AUTOA的平仓记录分别写入Excel的不同sheet
    特点：
        - 线程安全：使用锁保护写入操作
        - 自动创建：文件不存在时自动创建
        - 分sheet存储：AUTOBN写入"币安期货"，AUTOA写入"A股"
        - 追加模式：每次平仓追加一行记录
    """

    IO_TIMEOUT_SECONDS = 15
    _lock = threading.Lock()
    _excel_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "close_records.xlsx"
    )
    _logger = logging.getLogger("CloseRecordManager")

    # Sheet名称映射
    SHEET_NAMES = {
        "AUTOBN": "币安期货",
        "AUTOA": "A股",
    }

    # Excel列定义
    COLUMNS = [
        "平仓时间",
        "交易品种",  # symbol 或 股票代码
        "持仓方向",  # LONG/SHORT
        "开仓价格",
        "平仓价格",
        "平仓数量",
        "平仓盈亏(USDT/CNY)",
        "平仓收益率",
        "平仓比例",
        "策略标签",  # Supertrend/BZ/BD 等
        "平仓依据",
    ]

    @classmethod
    def record_close(
        cls,
        source: str,  # "AUTOBN" 或 "AUTOA"
        symbol: str,
        position_side: str,
        entry_price: float,
        close_price: float,
        close_amount: float,
        realized_pnl: float,
        pnl_percent: float,
        close_ratio: float = 1.0,
        strategy_tag: str = "",
        close_reason: str = "",
    ):
        """
        记录一笔平仓交易

        参数：
            source: 交易来源 ("AUTOBN" 或 "AUTOA")
            symbol: 交易品种（如'BTCUSDT'或'000001'）
            position_side: 持仓方向（'LONG'或'SHORT'）
            entry_price: 开仓价格
            close_price: 平仓价格
            close_amount: 平仓数量
            realized_pnl: 平仓盈亏（USDT或CNY）
            pnl_percent: 平仓收益率
            close_ratio: 平仓比例（默认1.0表示全平）
            strategy_tag: 策略标签（如'Supertrend'、'BZ'等）
        """
        with cls._lock:
            try:
                close_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sheet_name = cls.SHEET_NAMES.get(source, source)

                # 准备新记录（不再包含交易来源列，因为已经分sheet）
                new_record = {
                    "平仓时间": close_time,
                    "交易品种": symbol,
                    "持仓方向": position_side,
                    "开仓价格": entry_price,
                    "平仓价格": close_price,
                    "平仓数量": close_amount,
                    "平仓盈亏(USDT/CNY)": realized_pnl,
                    "平仓收益率": f"{pnl_percent:.2%}",
                    "平仓比例": f"{close_ratio:.2%}",
                    "策略标签": strategy_tag,
                    "平仓依据": close_reason,
                }

                # 读取现有数据
                existing_sheets = {}
                if os.path.exists(cls._excel_file):
                    try:
                        # 读取所有现有sheet
                        with pd.ExcelFile(cls._excel_file, engine="openpyxl") as xls:
                            for name in xls.sheet_names:
                                existing_sheets[name] = pd.read_excel(
                                    xls, sheet_name=name
                                )
                    except Exception:
                        pass

                # 获取或创建目标sheet的DataFrame
                if sheet_name in existing_sheets:
                    df = existing_sheets[sheet_name]
                else:
                    df = pd.DataFrame(columns=cls.COLUMNS)

                # 追加新记录
                new_df = pd.DataFrame([new_record])
                df = pd.concat([df, new_df], ignore_index=True)
                existing_sheets[sheet_name] = df

                # 写入Excel（所有sheet）
                with pd.ExcelWriter(cls._excel_file, engine="openpyxl") as writer:
                    for name, data in existing_sheets.items():
                        data.to_excel(writer, sheet_name=name, index=False)

                cls._logger.info(
                    f"平仓记录已保存到[{sheet_name}]: {symbol} {position_side} "
                    f"盈亏:{realized_pnl:.4f} 收益率:{pnl_percent:.2%}"
                )

            except Exception as e:
                cls._logger.error(f"保存平仓记录失败: {str(e)}")
                cls._logger.exception("保存平仓记录时发生异常")

    @classmethod
    async def record_close_async(
        cls,
        source: str,
        symbol: str,
        position_side: str,
        entry_price: float,
        close_price: float,
        close_amount: float,
        realized_pnl: float,
        pnl_percent: float,
        close_ratio: float = 1.0,
        strategy_tag: str = "",
        close_reason: str = "",
    ):
        await asyncio.wait_for(
            asyncio.to_thread(
                cls.record_close,
                source,
                symbol,
                position_side,
                entry_price,
                close_price,
                close_amount,
                realized_pnl,
                pnl_percent,
                close_ratio,
                strategy_tag,
                close_reason,
            ),
            timeout=cls.IO_TIMEOUT_SECONDS,
        )


class AUTOBN:
    """币安期货自动交易类"""

    # ==================== 并发控制常量 ====================
    MAX_CONCURRENT_REQUESTS = 8  # 最大并发请求数

    # ==================== 时间常量 ====================
    OBSERVATION_TIMEOUT_SECONDS = 24 * 60 * 60  # 观察记录超时时间（1天）
    RETRY_DELAY_SECONDS = 2  # 重试延迟（秒）
    CLOSE_RETRY_DELAY = 3  # 平仓重试延迟（秒）

    # ==================== K线相关常量 ====================
    KLINE_LIMIT = 96  # K线数据条数
    MIN_KLINE_FOR_ANALYSIS = 4  # 分析所需最小K线数量

    # ==================== 多空比相关常量 ====================
    LONG_SHORT_RATIO_LIMIT = 30  # 多空比数据查询数量限制
    LONG_SHORT_RATIO_CACHE_TTL = 900  # 多空比缓存过期时间（秒）
    OI_5M_CACHE_TTL = 300  # 5分钟持仓量缓存过期时间（秒）
    LONG_SHORT_RATIO_LONG_LIMIT = 3 / 7  # LONG额外放行阈值（多空比）
    LONG_SHORT_RATIO_SHORT_LIMIT = 7 / 3  # SHORT额外放行阈值（多空比）
    OI_DELTA_LONG_RATIO_WEIGHT = 0.5  # LONG融合公式中(oi_5m-oi_1h)项权重

    # ==================== ATR风控常量 ====================
    ATR_PERIOD = 10  # ATR计算周期
    SUPERTREND_FACTOR = 3.0  # ATR倍数，用于计算止盈止损和supertrend上下轨
    ATR_TRIGGER_CAP_RATIO = 0.05
    ATR_HL2_CAP_RATIO = 0.1  # ATR返回值上限比例（不超过hl2的10%）
    MIN_ATR_TRIGGER = 1e-8
    DCA_TP_ATR_RATIO = 0.5  # DCA触发后止盈收紧系数(按ATR与触发次数)
    STOP_LOSS_DECAY_PER_MINUTE = 0.0001  # 每分钟止盈止损衰减比例 (0.01%)

    # ==================== 回溯周期常量 ====================
    OI_LOOKBACK_PERIOD = 10  # 持仓量检查回溯周期
    VOLUME_LOOKBACK_PERIOD = 10  # 成交量检查回溯周期
    OI_QUERY_LIMIT = 30  # 持仓量数据查询数量限制
    TARGET_PROFIT_DIVISOR = 3.0  # 目标收益分割系数（用于计算1/3收益触发点）

    # ==================== 风险管理常量 ====================
    RISK_PER_TRADE = 0.1  # 每笔交易风险比例 (10%: 止损触发时最多损失账户的10%)
    TARGET_PROFIT_RATIO = 0.1  # 每笔交易目标盈利比例 (10%: 止盈触发时赚取账户的10%)
    MAX_POSITION_RATIO = 0.1  # 单币种最大持仓比例 (防止极端杠杆)
    MAINTENANCE_MARGIN_RATE = 0.004  # 维持保证金率 (0.5%)

    # ==================== 切比雪夫概率阈值常量 ====================
    CHEBYSHEV_EXTREME_THRESHOLD = 0.01  # 极端异常阈值（1%），用于检测非常罕见的事件
    SHORT_OI_CHEB_THRESHOLD = 0.05  # SHORT的1d OI极端阈值（5%）

    # ==================== 基差率常量 ====================
    BASIS_RATE_THRESHOLD = 0.02  # 基差率开仓阈值（2%）
    BASIS_RATE_CACHE_TTL = 300  # 基差率缓存过期时间（秒，5分钟）

    # ==================== 平仓相关常量 ====================
    PARTIAL_CLOSE_RATIO = 0.7  # 部分平仓比例 (止盈时使用)
    TRAILING_STOP_PROFIT_RATIO = 0.7  # 追踪止损盈利保护比例 (保护70%盈利，允许30%回撤)
    MIN_NOTIONAL = 10  # 最小交易金额 (USDT)

    # ==================== 任务控制常量 ====================
    MAX_RETRY_COUNT = 10  # 最大重试次数
    EARLY_MORNING_HOUR = 8  # 早盘检测小时
    MARKET_ANALYSIS_TIMEOUT = 55  # 市场分析任务总超时时间（秒）
    API_TIMEOUT_SECONDS = 15  # 单次API调用超时时间（秒）
    BATCH_WINDOW_MINUTES = 5  # 分批窗口时长（分钟）
    BATCH_SLOT_COUNT = 5  # 窗口内批次数（每分钟一批）
    MESSAGE_TIMEOUT_SECONDS = 10  # 消息发送超时时间（秒）
    FILE_IO_TIMEOUT_SECONDS = 10  # 文件IO超时时间（秒）

    # ==================== 交易配置常量 ====================
    DEFAULT_LEVERAGE = 5  # 默认杠杆倍数
    DEFAULT_HEALTH_THRESHOLD = 70  # 默认健康度阈值（%）
    REOPEN_COOLDOWN_SECONDS = 24 * 60 * 60
    OPEN_LONG_SHORT_RATIO_THRESHOLD = 55 / 45
    DCA_LONG_SHORT_RATIO_THRESHOLD = 6 / 4
    OI_CHEB_EXCLUDE_RECENT_COUNT = 10
    MIN_CHEB_SAMPLE_SIZE = 2

    @classmethod
    def from_cfg(cls, **kwargs):
        obj = cls.__new__(cls)
        obj.symbols = []

        # 初始化日志记录器
        obj.logger = logging.getLogger(f"AUTOBN.{id(obj)}")
        obj.logger.setLevel(logging.INFO)  # 默认级别
        obj.logger.propagate = False  # 防止日志向上层传播导致重复

        # 如果没有处理器，则添加一个控制台处理器
        if not obj.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            obj.logger.addHandler(handler)

        # 基本配置：优先使用 kwargs，其次使用默认/环境
        # 支持键：qy_key, leverage, health4open, margin_mode/position_mode,
        #        session/session_verify/session_headers,
        #        wx_key, user_name,
        #        bn_api_file, alert_all_file/allert_all_file,
        #        api_key, api_secret, slot_balance
        obj.qy_key = kwargs.get("qy_key") or kwargs.get("qyWechatKey")
        if not obj.qy_key:
            raise ValueError("from_cfg 需要提供 qy_key")
        obj.signal_qy_key = kwargs.get("signal_qy_key") or obj.qy_key

        # 交易参数配置（可覆盖）
        obj.leverage = kwargs.get("leverage", cls.DEFAULT_LEVERAGE)
        obj.health4open = kwargs.get("health4open", cls.DEFAULT_HEALTH_THRESHOLD)

        # 仓位模式：'CROSSED' 全仓，'ISOLATED' 逐仓；支持大小写/中文/别名
        # 仅设置新开仓/下单前的目标模式；若该 symbol 已有仓位，交易所可能拒绝切换
        margin_mode_raw = (
            str(kwargs.get("margin_mode", kwargs.get("position_mode", "CROSSED")))
            .strip()
            .lower()
        )
        margin_mode_map = {
            "cross": "CROSSED",
            "crossed": "CROSSED",
            "全仓": "CROSSED",
            "全倉": "CROSSED",
            "c": "CROSSED",
            "isolated": "ISOLATED",
            "iso": "ISOLATED",
            "逐仓": "ISOLATED",
            "逐倉": "ISOLATED",
            "i": "ISOLATED",
        }
        obj.margin_mode = margin_mode_map.get(margin_mode_raw, "CROSSED")

        # 微信配置（可覆盖 -> 环境 -> 默认）
        obj.wx_key = kwargs.get(
            "wx_key", os.getenv("WX_KEY", "fe197940-30c1-4cea-a41a-17b461423f83")
        )
        obj.user_name = kwargs.get(
            "user_name", os.getenv("USER_NAME", "49124710049@chatroom")
        )
        bn_api_file = kwargs.get("bn_api_file", "bn.json")
        obj.alert_all_file = kwargs.get(
            "alert_all_file", kwargs.get("allert_all_file", "alert_all.json")
        )

        # 加载币安API配置并允许 kwargs 覆盖
        with open(bn_api_file, "r") as f:
            bn_api = json.load(f)

        # 优先级：kwargs参数 > JSON配置文件 > 环境变量
        api_key = (
            kwargs.get("api_key")
            or bn_api.get("api_key")
            or os.getenv("BINANCE_API_KEY")
        )
        api_secret = (
            kwargs.get("api_secret")
            or bn_api.get("api_secret")
            or os.getenv("BINANCE_API_SECRET")
        )

        # 安全检查：确保密钥已配置
        if not api_key or not api_secret:
            raise ValueError(
                "币安API密钥未配置！请通过以下方式之一提供：\n"
                "1. 在 bn.json 中配置 api_key 和 api_secret\n"
                "2. 设置环境变量 BINANCE_API_KEY 和 BINANCE_API_SECRET\n"
                "3. 在调用 from_cfg() 时传入 api_key 和 api_secret 参数"
            )

        # 初始化币安统一账户(PAPI)交易客户端 + 官方 USDS-M 行情客户端
        market_config = ConfigurationRestAPI(
            api_key=api_key,
            api_secret=api_secret,
            timeout=5000,
        )
        obj.market_client = DerivativesTradingUsdsFutures(config_rest_api=market_config)
        papi_config = ConfigurationRestAPI(
            api_key=api_key,
            api_secret=api_secret,
            timeout=5000,
        )
        obj.papi_client = DerivativesTradingPortfolioMargin(config_rest_api=papi_config)
        obj._api_semaphore = asyncio.Semaphore(obj.MAX_CONCURRENT_REQUESTS)
        adapter = HTTPAdapter(pool_connections=32, pool_maxsize=32)
        obj.market_client.rest_api._session.mount("https://", adapter)
        obj.market_client.rest_api._session.mount("http://", adapter)

        # 加载持仓记录
        with open(obj.alert_all_file, "r", encoding="utf-8") as f:
            obj.alert_all = json.load(f)
        obj.alert_all.setdefault("CLOSE_TS", {})

        # 初始化资金槽位(用于资金管理)(可覆盖)
        # 含义:用于控制单次下单的资金使用上限(与 open_ratio 一起作用)
        obj.slot_balance = kwargs.get("slot_balance", [0.0])
        obj.symbols_info = {}
        obj.is_early_morning = False
        # 初始化多空比缓存: {symbol: {"data": [...], "timestamp": float}}
        obj._long_short_ratio_cache = {}
        # 初始化1d持仓量历史缓存: {symbol: {"data": [...], "target_date": int}}
        # target_date 是当天8点的时间戳(毫秒)，用于判断缓存是否过期（用于 check_side）
        obj._oi_1d_cache = {}
        # 初始化1h持仓量历史缓存: {symbol: {"data": [...], "target_date": int}}
        # target_date 是当前整点的时间戳(毫秒)，用于判断缓存是否过期（用于 check_oi）
        obj._oi_1h_cache = {}
        # 初始化5分钟持仓量缓存: {symbol: {"data": [...], "timestamp": float}}
        obj._oi_5m_cache = {}
        # 初始化基差率缓存: {symbol: {"data": float, "timestamp": float}}
        obj._basis_rate_cache = {}
        # 分批扫描窗口状态：每个窗口固定一份symbols快照，避免窗口内漂移
        obj._batch_window_id = None
        obj._batch_symbols_snapshot = []

        # 注册退出处理函数,在脚本退出时保存数据
        def save_on_exit():
            """脚本退出时保存alert_all数据到文件"""
            try:
                obj.logger.info(f"脚本退出,正在保存AUTOBN数据到 {obj.alert_all_file}...")
                with open(obj.alert_all_file, "w", encoding="utf-8") as f:
                    json.dump(obj.alert_all, f, ensure_ascii=False, indent=4)
                obj.logger.info("AUTOBN数据保存完成")
            except Exception as e:
                obj.logger.error(f"保存AUTOBN数据失败: {str(e)}")
                obj.logger.exception("保存AUTOBN数据时发生异常")

        atexit.register(save_on_exit)

        return obj

    @staticmethod
    def _model_to_dict(data):
        if data is None:
            return {}
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return [AUTOBN._model_to_dict(i) for i in data]
        if hasattr(data, "to_dict"):
            return data.to_dict()
        if hasattr(data, "model_dump"):
            return data.model_dump(by_alias=True, exclude_none=True)
        return data

    @classmethod
    def _unwrap_api_response(cls, data):
        if hasattr(data, "data") and callable(data.data):
            return cls._model_to_dict(data.data())
        return cls._model_to_dict(data)

    def _normalize_account_info(self, account_info=None):
        if account_info is None:
            account_info = self._unwrap_api_response(
                self.papi_client.rest_api.account_information()
            )
        total_available_balance = float(
            account_info.get("totalAvailableBalance", 0) or 0
        )
        account_equity = float(account_info.get("accountEquity", 0) or 0)
        account_maint_margin = float(account_info.get("accountMaintMargin", 0) or 0)
        return {
            "availableBalance": total_available_balance,
            "totalWalletBalance": account_equity,
            "totalMarginBalance": account_equity,
            "accountMaintMargin": account_maint_margin,
            "raw": account_info,
        }

    def _normalize_position_risk(self, position_risk=None):
        if position_risk is None:
            position_risk = self._unwrap_api_response(
                self.papi_client.rest_api.query_um_position_information()
            )
        normalized_positions = []
        for row in position_risk or []:
            data = self._model_to_dict(row)
            amount = float(data.get("positionAmt", 0) or 0)
            if amount == 0:
                continue
            notional = abs(float(data.get("notional", 0) or 0))
            un_realized_profit = float(data.get("unRealizedProfit", 0) or 0)
            maint_margin = float(
                data.get("maintMargin", 0) or notional * self.MAINTENANCE_MARGIN_RATE
            )
            normalized_positions.append(
                {
                    "symbol": data.get("symbol"),
                    "entryPrice": str(data.get("entryPrice", 0) or 0),
                    "markPrice": str(data.get("markPrice", 0) or 0),
                    "positionAmt": str(data.get("positionAmt", 0) or 0),
                    "notional": str(data.get("notional", 0) or 0),
                    "unRealizedProfit": str(un_realized_profit),
                    "positionSide": data.get("positionSide") or PositionSide.LONG.value,
                    "maintMargin": str(maint_margin),
                }
            )
        return normalized_positions

    @staticmethod
    def _to_papi_side(side):
        return NewUmOrderSideEnum(side)

    @staticmethod
    def _to_papi_position_side(position_side):
        return NewUmOrderPositionSideEnum(position_side)

    @staticmethod
    def _to_papi_order_type(order_type):
        return NewUmOrderTypeEnum(order_type)

    def _new_order_via_papi(self, symbol, side, quantity, position_side):
        return self._unwrap_api_response(
            self.papi_client.rest_api.new_um_order(
                symbol=symbol,
                side=self._to_papi_side(side),
                type=self._to_papi_order_type("MARKET"),
                quantity=quantity,
                position_side=self._to_papi_position_side(position_side),
            )
        )

    def _change_leverage_via_papi(self, symbol, leverage):
        return self._unwrap_api_response(
            self.papi_client.rest_api.change_um_initial_leverage(
                symbol=symbol,
                leverage=leverage,
            )
        )

    async def send_msg(
        self, msg: str, wx: bool = False, qy_key: Optional[str] = None
    ) -> None:
        """
        发送消息通知函数

        功能：通过企业微信或微信发送交易通知消息

        参数：
            msg: 要发送的消息内容
            wx: 是否使用微信发送（True=微信，False=企业微信）
            qy_key: 可选的企业微信机器人key，未提供时默认使用 self.qy_key

        返回：
            None
        """
        try:
            self.logger.info(f"发送消息: {msg}")

            def _post_message():
                if wx:
                    json_msg = {
                        "MsgItem": [
                            {
                                "AtWxIDList": ["string"],
                                "ImageContent": "",
                                "MsgType": 0,
                                "TextContent": msg,
                                "ToUserName": self.user_name,
                            }
                        ]
                    }
                    return session.post(
                        f"http://wechatpadpro:1238/message/SendTextMessage?key={self.wx_key}",
                        json=json_msg,
                        timeout=self.MESSAGE_TIMEOUT_SECONDS,
                    )

                json_msg = {"msgtype": "text", "text": {"content": msg}}
                return session.post(
                    url=f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={qy_key or self.qy_key}",
                    json=json_msg,
                    timeout=self.MESSAGE_TIMEOUT_SECONDS,
                )

            response = await asyncio.wait_for(
                asyncio.to_thread(_post_message), timeout=self.MESSAGE_TIMEOUT_SECONDS
            )
            if response.status_code != 200:
                self.logger.error(f"消息发送失败，状态码: {response.status_code}")
        except Exception as e:
            self.logger.error(f"消息发送异常: {str(e)}")

    async def calculate_health_bn(self, notional, account_data=None) -> int:
        """计算统一账户健康度（首版按账户权益/维保近似）"""
        if account_data is None:
            account_data = await self._call_api(
                self.papi_client.rest_api.account_information,
                recv_window=60000,
            )
            account_data = self._normalize_account_info(account_data)
        total_balance = float(account_data["totalMarginBalance"])

        position_data = await self._call_api(
            self.papi_client.rest_api.query_um_position_information
        )
        position_data = self._normalize_position_risk(position_data)
        total_maintenance_margin = sum(
            float(position.get("maintMargin", 0) or 0) for position in position_data
        )
        if not account_data.get("accountMaintMargin"):
            total_maintenance_margin += notional * self.MAINTENANCE_MARGIN_RATE

        if total_maintenance_margin == 0 and total_balance >= 0:
            return 100
        if total_balance <= 0:
            return 0
        return round(
            min(100, max(0, (1 - total_maintenance_margin / total_balance) * 100))
        )

    async def _call_api(self, method, *args, **kwargs):
        """统一异步调用入口，兼容 PAPI ApiResponse 和普通返回值"""
        async with self._api_semaphore:
            result = await asyncio.wait_for(
                asyncio.to_thread(method, *args, **kwargs),
                timeout=self.API_TIMEOUT_SECONDS,
            )
            return self._unwrap_api_response(result)

    async def _call_um(self, method, *args, **kwargs):
        """兼容旧调用名，内部统一走 _call_api"""
        return await self._call_api(method, *args, **kwargs)

    async def get_amount_close(self, symbol):
        """
        获取指定交易对的持仓数量 (异步)

        功能：查询币安账户中指定交易对的当前持仓数量
        用途：用于平仓时确定需要平仓的数量
        参数：
            symbol: 交易对符号，如'BTCUSDT'
        返回：
            持仓数量（绝对值），无持仓返回0
        """
        try:
            position_risk = await self._call_api(
                self.papi_client.rest_api.query_um_position_information,
                symbol=symbol,
                recv_window=60000,
            )
            normalized_positions = self._normalize_position_risk(position_risk)
            position = {
                k["symbol"]: [abs(float(k["positionAmt"])), float(k["entryPrice"])]
                for k in normalized_positions
            }
            return position.get(symbol, [0, 0])
        except Exception:
            return 0

    async def open_bn_position(
        self,
        symbol,
        side,
        positionSide,
        take_profit_price=None,
        stop_loss_price=None,
        open_info=None,
    ):
        """
        在币安期货市场开仓 (风险定仓位模型) - 异步版本

        功能：执行开仓操作，基于止损距离动态计算仓位大小
        参数：
            symbol: 交易对符号，如'BTCUSDT'
            side: 交易方向，'BUY'或'SELL'
            positionSide: 持仓方向，'LONG'或'SHORT'
            stop_loss_price: 止损价格 (必填，用于计算风险仓位)
            open_info: Observation对象，包含策略信息（用于消息通知）
        返回：
            成功返回account_data，失败返回None
        """
        try:
            account_data_raw, mark_price_data = await asyncio.gather(
                self._call_api(
                    self.papi_client.rest_api.account_information,
                    recv_window=60000,
                ),
                self._call_api(
                    self.market_client.rest_api.mark_price,
                    symbol=symbol,
                ),
            )
            account_data = self._normalize_account_info(account_data_raw)

            balance = float(account_data["availableBalance"])
            if balance <= 0:
                await self.send_msg(f"{symbol} 开仓失败：可用余额为零")
                return None

            if not mark_price_data:
                await self.send_msg(f"{symbol} 开仓失败：无法获取标记价格")
                return None

            markPrice = float(mark_price_data["markPrice"])

            if symbol not in self.symbols_info:
                await self.send_msg(f"{symbol} 开仓失败：找不到交易对信息")
                return None

            if stop_loss_price is None or stop_loss_price <= 0:
                await self.send_msg(f"{symbol} 开仓失败：未提供有效止损价格")
                return None
            if take_profit_price is None or take_profit_price <= 0:
                await self.send_msg(f"{symbol} 开仓失败：未提供有效止盈价格")
                return None

            stop_loss_gap = abs(markPrice - stop_loss_price)
            take_profit_gap = abs(take_profit_price - markPrice)

            if stop_loss_gap <= 0 or take_profit_gap <= 0:
                await self.send_msg(f"{symbol} 开仓失败：止损/止盈距离为零")
                return None

            total_balance = float(account_data["totalWalletBalance"])
            risk_amount = total_balance * self.RISK_PER_TRADE
            target_profit = total_balance * self.TARGET_PROFIT_RATIO

            amount_by_sl = risk_amount / stop_loss_gap
            amount_by_tp = target_profit / take_profit_gap
            amount_raw = (amount_by_sl + amount_by_tp) / 2

            max_notional = balance * self.MAX_POSITION_RATIO
            max_amount = max_notional / markPrice
            if amount_raw > max_amount:
                self.logger.warning(
                    f"{symbol} 风险仓位 {amount_raw:.4f} 超限，限制为 {max_amount:.4f}"
                )
                amount_raw = max_amount

            amount = float(
                Decimal(str(amount_raw)).quantize(
                    self.symbols_info.get(symbol)["quantityPrecision"],
                    rounding=ROUND_DOWN,
                )
            )

            notional = amount * markPrice

            if notional < self.MIN_NOTIONAL:
                return None

            required_margin = notional / self.leverage
            if required_margin > balance:
                return None

            account_health = await self.calculate_health_bn(notional, account_data)
            if account_health < self.health4open:
                return None

            leverage_result = await self._call_api(
                self.papi_client.rest_api.change_um_initial_leverage,
                symbol=symbol,
                leverage=self.leverage,
                recv_window=60000,
            )
            actual_leverage = leverage_result.get("leverage", self.leverage)

            tx = await self._call_api(
                self.papi_client.rest_api.new_um_order,
                symbol=symbol,
                side=self._to_papi_side(side),
                type=self._to_papi_order_type("MARKET"),
                quantity=amount,
                position_side=self._to_papi_position_side(positionSide),
                recv_window=60000,
            )
            rate_show = abs(take_profit_price - markPrice) / markPrice
            msg = f"{symbol} 开仓\n策略:{','.join([ps.value for ps in open_info.strategy])}\n持仓方向:{positionSide}\n杠杆:{actual_leverage}x\n委托数量:{tx.get('origQty', 0)}\n委托价格:{markPrice}\n名义价值:{notional} USDT\n账户余额:{total_balance:.2f}\n仓位比例:{notional / total_balance:.2%}\n收益率:{rate_show:.2%}"
            await self.send_msg(msg)
            return account_data
        except Exception as e:
            error_msg = f"{symbol} 开仓失败：{str(e)}"
            self.logger.exception(error_msg)
            return None

    async def close_bn_position(
        self,
        symbol,
        close_info,
        atr_value,
        price_close,
        close_ratio=1.0,
    ):
        """
        在币安期货市场平仓 (异步版本)

        功能：执行平仓操作，支持重试机制确保成功，成功后记录到Excel
        参数：
            symbol: 交易对符号，如'BTCUSDT'
            close_info: Position对象，包含止盈止损、平仓方向、持仓方向、策略标签等信息
            atr_value: ATR值，用于部分平仓后重新计算止盈止损，为0时不更新
            price_close: 当前价格（用于通知和盈亏计算）
            close_ratio: 平仓比例，1.0表示全部平仓，0.5表示平仓50%
        返回：
            成功返回symbol，失败返回None
        """
        amount_price = await self.get_amount_close(symbol)
        amount = amount_price[0]
        if not amount:
            return
        close_ratio = (
            1 if amount * close_ratio * price_close < self.MIN_NOTIONAL else close_ratio
        )
        close_amount = amount * close_ratio
        close_amount = float(
            Decimal(str(close_amount)).quantize(
                self.symbols_info.get(symbol)["quantityPrecision"], rounding=ROUND_DOWN
            )
        )
        if close_amount <= 0:
            self.alert_all["POSITIONS"].pop(symbol)
            return
        side = close_info.close_side.value
        positionSide = close_info.position_side.value
        while close_amount > 0:
            try:
                tx = await self._call_api(
                    self.papi_client.rest_api.new_um_order,
                    symbol=symbol,
                    side=self._to_papi_side(side),
                    type=self._to_papi_order_type("MARKET"),
                    quantity=close_amount,
                    position_side=self._to_papi_position_side(positionSide),
                    recv_window=60000,
                )
                entryPrice = (
                    amount_price[1] if amount_price[1] > 0 else close_info.entry_price
                )

                price_diff = (
                    price_close - entryPrice
                    if positionSide == PositionSide.LONG.value
                    else entryPrice - price_close
                )
                realized_pnl = price_diff * close_amount
                pnl_percent = price_diff / entryPrice if entryPrice != 0 else 0
                strategy_tag = ",".join([ps.value for ps in close_info.strategy])
                msg = f"{symbol} 平仓\n策略:{strategy_tag}\n持仓方向:{positionSide}\n委托价格:{price_close}\n委托数量:{tx.get('origQty', 0)}\n平仓比例:{close_ratio:.2%}\n平仓盈亏:{realized_pnl} USDT\n平仓收益:{pnl_percent:.2%}\n止盈次数:{close_info.tp_count}\n平仓依据:{close_info.close_reason}"
                await self.send_msg(msg)

                await CloseRecordManager.record_close_async(
                    source="AUTOBN",
                    symbol=symbol,
                    position_side=positionSide,
                    entry_price=entryPrice,
                    close_price=price_close,
                    close_amount=close_amount,
                    realized_pnl=realized_pnl,
                    pnl_percent=pnl_percent,
                    close_ratio=close_ratio,
                    strategy_tag=strategy_tag,
                    close_reason=close_info.close_reason,
                )

                remaining_amount_price = await self.get_amount_close(symbol)
                remaining_amount = remaining_amount_price[0]
                if remaining_amount == 0:
                    self.alert_all.setdefault("CLOSE_TS", {})[symbol] = time.time()
                    if symbol in self.alert_all["POSITIONS"]:
                        self.alert_all["POSITIONS"].pop(symbol)
                elif atr_value > 0:
                    is_long = positionSide == PositionSide.LONG.value
                    new_tp, new_sl = self.calc_stop_profit_loss(
                        price_close,
                        is_long=is_long,
                        atr=atr_value,
                    )
                    if new_tp > 0 and new_sl > 0:
                        if is_long:
                            close_info.take_profit = new_tp
                            close_info.stop_loss = new_sl
                        else:
                            close_info.take_profit = new_sl
                            close_info.stop_loss = new_tp

                    self.alert_all["POSITIONS"][symbol] = close_info.model_dump()
                return symbol
            except Exception:
                await asyncio.sleep(self.CLOSE_RETRY_DELAY)
                self.logger.exception(f"平仓 {symbol} 失败，当前价格: {price_close}")
                msg = f"bn平仓{symbol}失败，当前价格:{price_close}"
                await self.send_msg(msg)
                current_amount_price = await self.get_amount_close(symbol)
                close_amount = current_amount_price[0] * close_ratio
                close_amount = float(
                    Decimal(str(close_amount)).quantize(
                        self.symbols_info.get(symbol)["quantityPrecision"],
                        rounding=ROUND_DOWN,
                    )
                )
        return None

    async def _get_oi_5m_data(self, symbol):
        """获取5m OI数据（优先缓存）"""
        current_time_5m = time.time()
        oi_5m_cache = self._oi_5m_cache.get(symbol)
        if (
            oi_5m_cache
            and (current_time_5m - oi_5m_cache["timestamp"]) < self.OI_5M_CACHE_TTL
        ):
            return oi_5m_cache["data"]

        oi_5m = await self._call_api(
            self.market_client.rest_api.open_interest_statistics,
            symbol=symbol,
            period="5m",
            limit=self.OI_QUERY_LIMIT,
        )
        self._oi_5m_cache[symbol] = {
            "data": oi_5m,
            "timestamp": current_time_5m,
        }
        return oi_5m

    async def _get_oi_1h_data(self, symbol, dtn: datetime):
        """获取1h OI数据（优先缓存，按当前整点对齐）"""
        dtn_target_1h = dtn.replace(minute=0, second=0, microsecond=0)
        target_ts_1h = int(dtn_target_1h.timestamp() * 1000)
        oi_1h_cache = self._oi_1h_cache.get(symbol)
        if oi_1h_cache and oi_1h_cache.get("target_date") == target_ts_1h:
            return oi_1h_cache["data"]

        oi_1h = await self._call_api(
            self.market_client.rest_api.open_interest_statistics,
            symbol=symbol,
            period="1h",
            limit=self.OI_QUERY_LIMIT,
        )
        if oi_1h and oi_1h[-1]["timestamp"] == target_ts_1h:
            self._oi_1h_cache[symbol] = {
                "data": oi_1h,
                "target_date": target_ts_1h,
            }
        return oi_1h

    async def check_side(
        self,
        semaphore,
        symbol,
        positionSide,
        kline_close=None,
        dtn: datetime = None,
    ):
        """
        检查增仓信号，判断是否适合开仓
        """
        async with semaphore:
            try:
                if positionSide == PositionSide.SHORT.value:
                    oi_5m = await self._get_oi_5m_data(symbol)
                    if not oi_5m:
                        return False, None, None
                    oi_5m_last = float(oi_5m[-1]["sumOpenInterest"])

                    # 获取持仓量历史数据（带缓存，仅做空使用）
                    dtn_target = dtn.replace(hour=8, minute=0, second=0, microsecond=0)
                    target_ts = int(dtn_target.timestamp() * 1000)

                    # 检查缓存是否存在且有效（target_date 匹配当天8点）
                    cache_entry = self._oi_1d_cache.get(symbol)
                    if cache_entry and cache_entry.get("target_date") == target_ts:
                        # 缓存有效，直接使用
                        oi_1d = cache_entry["data"]
                    else:
                        # 缓存无效或不存在，获取新数据
                        oi_1d = await self._call_api(
                            self.market_client.rest_api.open_interest_statistics,
                            symbol=symbol,
                            period="1d",
                            limit=self.OI_QUERY_LIMIT,
                        )
                        # 检查数据是否满足条件
                        if oi_1d[-1]["timestamp"] != target_ts:
                            return False, None, None
                        # 数据满足条件，缓存起来
                        self._oi_1d_cache[symbol] = {
                            "data": oi_1d,
                            "target_date": target_ts,
                        }
                    sumOpenInterest_1d = [
                        float(i["sumOpenInterest"]) for i in oi_1d
                    ]  # 持仓数量（合约数）
                    oi_hist_for_cheb = sumOpenInterest_1d[
                        -(self.OI_QUERY_LIMIT - self.OI_CHEB_EXCLUDE_RECENT_COUNT) :
                    ]
                    if len(oi_hist_for_cheb) < self.MIN_CHEB_SAMPLE_SIZE:
                        return False, None, None

                    passed = (
                        oi_5m_last <= min(sumOpenInterest_1d)
                        and self.calculate_chebyshev_probability(
                            oi_hist_for_cheb,
                            oi_5m_last,
                        )["chebyshev_upper_bound"]
                        < self.SHORT_OI_CHEB_THRESHOLD
                    )
                    return (True, None, None) if passed else (False, None, None)

                # 获取多空人数比数据（使用缓存）
                long_short_ratio_data = await self.get_long_short_ratio(symbol)
                # 提取最新的多空人数比
                if not long_short_ratio_data:
                    return False, None, None

                # 提取所有历史多空比值
                lsr_values = [
                    float(item["longShortRatio"]) for item in long_short_ratio_data
                ]
                lsrd = lsr_values[-1]  # 当前值

                # 多仓比例提取：优先 longAccount，缺失时由 longShortRatio 推导
                def _extract_long_ratio(item):
                    long_account = item.get("longAccount")
                    if long_account is not None:
                        return float(long_account)
                    lsr = float(item["longShortRatio"])
                    if lsr <= -1:
                        return None
                    return lsr / (1 + lsr)

                oi_5m = await self._get_oi_5m_data(symbol)

                if not oi_5m:
                    return False, None, None
                oi_5m_last = float(oi_5m[-1]["sumOpenInterest"])
                if positionSide == PositionSide.LONG.value:
                    if lsrd >= self.OPEN_LONG_SHORT_RATIO_THRESHOLD:
                        return False, None, None
                    long_extreme = len(lsr_values) >= 2 and lsrd <= min(lsr_values[:-1])
                    long_ratio_cond = lsrd < self.LONG_SHORT_RATIO_LONG_LIMIT
                    # 做多：极值条件 或 多空比阈值条件
                    if not (long_extreme or long_ratio_cond):
                        return False, None, None

                    target_ts_1h = int(
                        dtn.replace(minute=0, second=0, microsecond=0).timestamp()
                        * 1000
                    )
                    oi_1h = await self._get_oi_1h_data(symbol, dtn)

                    if not oi_1h:
                        return False, None, None
                    sumOpenInterest_1h = [float(i["sumOpenInterest"]) for i in oi_1h]
                    if len(sumOpenInterest_1h) < 1:
                        return False, None, None
                    oi_hist_for_cheb = sumOpenInterest_1h[
                        : -self.OI_CHEB_EXCLUDE_RECENT_COUNT
                    ]
                    if len(oi_hist_for_cheb) < self.MIN_CHEB_SAMPLE_SIZE:
                        return False, None, None

                    current_total_oi = oi_5m_last
                    if current_total_oi <= 0:
                        return False, None, None

                    latest_oi_1h = float(oi_1h[-1]["sumOpenInterest"])
                    latest_ratio_item_5m = long_short_ratio_data[-1]
                    long_ratio_5m = _extract_long_ratio(latest_ratio_item_5m)
                    if long_ratio_5m is None:
                        return False, None, None

                    ratio_item_1h = None
                    for item in reversed(long_short_ratio_data):
                        item_ts = item.get("timestamp")
                        if item_ts is None:
                            continue
                        if int(item_ts) == target_ts_1h:
                            ratio_item_1h = item
                            break

                    if ratio_item_1h is None:
                        for item in reversed(long_short_ratio_data):
                            item_ts = item.get("timestamp")
                            if item_ts is None:
                                continue
                            try:
                                if int(item_ts) <= target_ts_1h:
                                    ratio_item_1h = item
                                    break
                            except Exception:
                                continue

                    if ratio_item_1h is None:
                        return False, None, None

                    long_ratio_1h = _extract_long_ratio(ratio_item_1h)
                    if long_ratio_1h is None:
                        return False, None, None

                    blend = (
                        latest_oi_1h * long_ratio_1h
                        + (oi_5m_last - latest_oi_1h) * self.OI_DELTA_LONG_RATIO_WEIGHT
                    ) / current_total_oi

                    if blend <= long_ratio_5m:
                        return False, None, None

                    passed = (
                        oi_5m_last >= max(sumOpenInterest_1h)
                        and self.calculate_chebyshev_probability(
                            oi_hist_for_cheb,
                            oi_5m_last,
                        )["chebyshev_upper_bound"]
                        < self.CHEBYSHEV_EXTREME_THRESHOLD
                    )
                    oi_guard_threshold = max(oi_hist_for_cheb)
                    return (
                        (True, lsrd, oi_guard_threshold)
                        if passed
                        else (False, None, None)
                    )

            except Exception:
                self.logger.exception("检查增仓信号时发生错误")
                return False, None, None

    async def get_kline(self, semaphore, symbol, t: str):
        """
        异步获取K线数据

        功能：从币安获取指定交易对的K线数据
        参数：
            semaphore: 异步信号量，控制并发数量
            symbol: 交易对符号，如'BTCUSDT'
            t: 时间周期，如'1Dutc'（1天UTC时间）
        返回：
            K线数据列表，每个元素包含[开盘时间, 开盘价, 最高价, 最低价, 收盘价, 成交量, ...]
        """
        async with semaphore:
            # 提取时间周期前缀并转小写（如'1Dutc' -> '1d'）
            interval = t.replace("utc", "").lower()
            try:
                # 异步获取K线数据
                kline = await self._call_api(
                    self.market_client.rest_api.kline_candlestick_data,
                    symbol=symbol,
                    interval=interval,
                    limit=self.KLINE_LIMIT,
                )
                # 将所有数据转换为浮点数格式
                return [list(map(float, sublist)) for sublist in kline]
            except Exception as e:
                self.logger.error(f"{symbol}获取K线数据失败: {str(e)}")
                # 获取失败时返回空列表
                return []

    async def get_long_short_ratio(self, symbol: str, force_refresh: bool = False):
        """
        获取多空人数比数据（带缓存）

        功能：从币安获取指定交易对的多空人数比数据，结果会被缓存
        参数：
            symbol: 交易对符号，如'BTCUSDT'
            force_refresh: 是否强制刷新缓存，默认False
        返回：
            多空人数比数据列表，缓存失效或强制刷新时重新获取
        """
        current_time = time.time()
        cache_entry = self._long_short_ratio_cache.get(symbol)

        # 检查缓存是否有效
        if (
            not force_refresh
            and cache_entry
            and (current_time - cache_entry["timestamp"])
            < self.LONG_SHORT_RATIO_CACHE_TTL
        ):
            data = cache_entry["data"]
        else:
            # 缓存无效或强制刷新，重新获取数据
            try:
                data = await self._call_api(
                    self.market_client.rest_api.long_short_ratio,
                    symbol=symbol,
                    period="1h",
                    limit=self.LONG_SHORT_RATIO_LIMIT,
                )
                # 更新缓存
                self._long_short_ratio_cache[symbol] = {
                    "data": data,
                    "timestamp": current_time,
                }
            except Exception as e:
                self.logger.error(f"{symbol}获取多空比数据失败: {str(e)}")
                # 如果获取失败但有旧缓存，返回旧数据
                if cache_entry:
                    data = cache_entry["data"]
                else:
                    data = []
        try:
            data2 = await self._call_api(
                self.market_client.rest_api.long_short_ratio,
                symbol=symbol,
                period="5m",
                limit=1,
            )
        except Exception as e:
            self.logger.error(f"{symbol}获取多空比数据失败: {str(e)}")
            data2 = []
        return data + data2

    async def get_basis_rate(self, symbol: str) -> float:
        """
        获取指定交易对的基差率（带5分钟缓存）

        基差率 = (期货价格 - 指数价格) / 指数价格
        - 基差率 > 0：期货升水（期货价格高于现货）
        - 基差率 < 0：期货贴水（期货价格低于现货）

        参数:
            symbol: 交易对符号，如'BTCUSDT'
        返回:
            基差率（浮点数），获取失败返回0
        """
        try:
            # 检查缓存是否有效
            current_time = time.time()
            cache_entry = self._basis_rate_cache.get(symbol)
            if (
                cache_entry
                and (current_time - cache_entry["timestamp"])
                < self.BASIS_RATE_CACHE_TTL
            ):
                return cache_entry["data"]

            # 获取指数价格和标记价格（统一受全局并发闸门约束）
            premium_index = await self._call_api(
                self.market_client.rest_api.mark_price,
                symbol=symbol,
            )
            if not premium_index:
                return 0.0

            index_price = float(premium_index.get("indexPrice", 0))
            mark_price = float(premium_index.get("markPrice", 0))

            if index_price <= 0:
                return 0.0

            # 基差率 = (期货价格 - 指数价格) / 指数价格
            basis_rate = (mark_price - index_price) / index_price

            # 更新缓存
            self._basis_rate_cache[symbol] = {
                "data": basis_rate,
                "timestamp": current_time,
            }

            return basis_rate
        except Exception as e:
            self.logger.error(f"{symbol} 获取基差率失败: {str(e)}")
            return 0.0

    def calculate_atr(self, kline_data, period=None):
        """
        计算ATR (平均真实波幅) - 使用 Wilder's Smoothing (RMA)
        """
        if period is None:
            period = self.ATR_PERIOD
        if not kline_data or len(kline_data) < period + 1:
            return 0.0

        tr_list = []
        for i in range(1, len(kline_data)):
            high = kline_data[i][2]
            low = kline_data[i][3]
            prev_close = kline_data[i - 1][4]

            # TR = Max(H-L, |H-PC|, |L-PC|)
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)

        if len(tr_list) < period:
            return 0.0

        # Wilder's Smoothing (RMA)
        # 第一个 ATR 使用 SMA
        atr = sum(tr_list[:period]) / period
        # 之后使用指数平滑
        for i in range(period, len(tr_list)):
            atr = (atr * (period - 1) + tr_list[i]) / period

        hl2 = (kline_data[-1][2] + kline_data[-1][3]) / 2
        atr_cap = hl2 * self.ATR_HL2_CAP_RATIO
        return min(atr, atr_cap) if atr_cap > 0 else atr

    # 止盈止损计算辅助函数 (使用supertrend的factor倍ATR)
    def calc_stop_profit_loss(self, price, is_long=True, atr=0):
        if atr <= 0:
            return (0, 0)

        # 使用supertrend的factor倍ATR作为止盈止损距离
        atr_distance = atr * self.SUPERTREND_FACTOR
        if is_long:
            return (price + atr_distance, price - atr_distance)
        else:
            # 做空：返回 (下界/止盈位, 上界/止损位)
            return (price - atr_distance, price + atr_distance)

    def calculate_chebyshev_probability(self, data_list, value):
        """
        计算给定数值对应的切比雪夫概率

        功能：根据切比雪夫不等式计算给定数值在数据分布中的概率特征

        切比雪夫不等式：P(|X - μ| >= kσ) <= 1/k²
        换言之：至少有 (1 - 1/k²) 的数据落在 [μ - kσ, μ + kσ] 区间内

        参数：
            data_list: 数据列表（如价格列表、收益率列表等）
            value: 给定的数值，用于计算其在分布中的位置

        返回：
            字典，包含以下信息：
            - mean: 数据均值
            - std: 数据标准差
            - k: 给定数值距离均值的标准差倍数
            - chebyshev_upper_bound: 切比雪夫不等式的上界概率 (1/k²)
            - min_probability_in_range: 至少有该比例的数据在 k 个标准差范围内 (1 - 1/k²)
            - deviation: 给定数值与均值的偏差

        示例：
            >>> prices = [100, 102, 98, 101, 99, 103, 97]
            >>> result = calculate_chebyshev_probability(prices, 110)
            >>> print(f"均值: {result['mean']}, 标准差: {result['std']}")
            >>> print(f"数值 110 距离均值 {result['k']:.2f} 个标准差")
            >>> print(f"根据切比雪夫不等式，至少有 {result['min_probability_in_range']:.2%} 的数据")
            >>> print(f"落在均值 ± {result['k']:.2f} 个标准差范围内")
        """
        # 输入验证
        if not data_list or len(data_list) == 0:
            raise ValueError("数据列表不能为空")

        if len(data_list) == 1:
            return {
                "mean": data_list[0],
                "std": 0.0,
                "k": float("inf") if data_list[0] != value else 0.0,
                "chebyshev_upper_bound": 0.0,
                "min_probability_in_range": 1.0,
                "deviation": value - data_list[0],
                "message": "数据只有一个元素，标准差为0",
            }

        # 计算均值
        mean = sum(data_list) / len(data_list)

        # 计算标准差（样本标准差，使用 n-1 作为分母）
        variance = sum((x - mean) ** 2 for x in data_list) / (len(data_list) - 1)
        std = variance**0.5

        # 计算给定数值与均值的偏差
        deviation = value - mean

        # 如果标准差为0（所有数据相同）
        if std == 0:
            return {
                "mean": mean,
                "std": 0.0,
                "k": float("inf") if deviation != 0 else 0.0,
                "chebyshev_upper_bound": 0.0,
                "min_probability_in_range": 1.0,
                "deviation": deviation,
                "message": "所有数据相同，标准差为0",
            }

        # 计算 k 值（给定数值距离均值有多少个标准差）
        k = abs(deviation) / std

        # 切比雪夫不等式的上界：P(|X - μ| >= kσ) <= 1/k²
        # 只有当 k > 1 时，切比雪夫不等式才有意义
        if k <= 1:
            chebyshev_upper_bound = 1.0  # k <= 1 时，不等式给出的上界为 1（无信息）
            min_probability_in_range = 0.0
        else:
            chebyshev_upper_bound = 1 / (k**2)
            # 至少有 (1 - 1/k²) 的数据落在 [μ - kσ, μ + kσ] 区间内
            min_probability_in_range = 1 - chebyshev_upper_bound

        result = {
            "mean": mean,
            "std": std,
            "k": k,
            "chebyshev_upper_bound": chebyshev_upper_bound,
            "min_probability_in_range": min_probability_in_range,
            "deviation": deviation,
        }

        # 添加人类可读的解释
        if k <= 1:
            result["message"] = (
                f"数值 {value:.4f} 距离均值 {mean:.4f} 只有 {k:.4f} 个标准差（在 1σ 范围内），切比雪夫不等式不提供有用信息"
            )
        else:
            result["message"] = (
                f"数值 {value:.4f} 距离均值 {mean:.4f} 约 {k:.4f} 个标准差。"
                f"根据切比雪夫不等式，至少有 {min_probability_in_range:.2%} 的数据"
                f"落在 [μ - {k:.4f}σ, μ + {k:.4f}σ] 范围内，"
                f"即 [{mean - k * std:.4f}, {mean + k * std:.4f}] 区间。"
                f"超出此范围的数据比例不超过 {chebyshev_upper_bound:.2%}。"
            )

        return result

    async def rzq_token(self, semaphore, symbol, success, dtn):
        """
        核心交易逻辑：分析K线数据并执行交易决策
        """
        try:
            # 获取原始数据并转换为对象
            close_info_dict = self.alert_all["POSITIONS"].get(symbol)
            open_info_dict = self.alert_all["OBSERVATIONS"].get(symbol)

            close_info: Optional[Position] = (
                Position.model_validate(close_info_dict) if close_info_dict else None
            )
            open_info: Optional[Observation] = (
                Observation.model_validate(open_info_dict) if open_info_dict else None
            )

            # 获取日K线数据（30天）
            kline = await self.get_kline(semaphore, symbol, "1Dutc")
            # 数据量检查
            if len(kline) < self.MIN_KLINE_FOR_ANALYSIS:
                return
            success.add(symbol)
            kline_close = [k[4] for k in kline]
            kline_volume = [k[5] for k in kline]

            # 预计算常用值
            current_price = kline_close[-1]
            current_timestamp = dtn.timestamp()

            # 检查现有持仓是否需要平仓
            if close_info:
                # 获取15分钟K线数据用于ATR计算（与supertrend保持一致）
                atr_value = self.calculate_atr(kline)
                # 检测是否需要用ATR初始化止盈止损 (止盈或止损为0表示需要更新)
                if (
                    close_info.take_profit == 0 or close_info.stop_loss == 0
                ) and atr_value > 0:
                    is_long = close_info.position_side.value == PositionSide.LONG.value
                    # 使用hl2中间价计算止盈止损，与supertrend保持一致
                    hl2 = (kline[-1][2] + kline[-1][3]) / 2  # (high + low) / 2
                    tp, sl = self.calc_stop_profit_loss(
                        hl2, is_long=is_long, atr=atr_value
                    )
                    close_info.take_profit = tp
                    close_info.stop_loss = sl
                    order_side = OrderSide.BUY if is_long else OrderSide.SELL
                    # 转换为 Observation 对象并保存
                    open_info = Observation(
                        price=current_price,
                        timestamp=current_timestamp,
                        side=order_side,
                        strategy=[close_info.strategy[0]],
                        name=symbol,
                    )
                    # 更新到字典
                    self.alert_all["OBSERVATIONS"][symbol] = open_info.model_dump()
                    self.alert_all["POSITIONS"][symbol] = close_info.model_dump()
                    self.logger.info(
                        f"[ATR初始化] {symbol} 止盈:{close_info.take_profit:.2f} 止损:{close_info.stop_loss:.2f}"
                    )

                # 根据持仓方向判断止盈止损触发
                # 多头: take_profit=高价, stop_loss=低价
                # 空头: take_profit=低价, stop_loss=高价
                is_long = close_info.position_side.value == PositionSide.LONG.value
                prev_close_price = kline_close[-2]

                # 止损触发条件：
                # - 保护盈利类（止盈后追踪止损/追踪止损）使用当前价触发
                # - 初始止损要求“当前价与昨收同时满足”，用多空最值实现
                # - 其他止损使用昨日收盘价触发
                use_current_price_sl = close_info.close_reason in (
                    "止盈后追踪止损",
                    "追踪止损(保护盈利)",
                )
                if use_current_price_sl:
                    sl_ref_price = current_price
                elif not close_info.close_reason:
                    sl_ref_price = (
                        max(current_price, prev_close_price)
                        if is_long
                        else min(current_price, prev_close_price)
                    )
                else:
                    sl_ref_price = prev_close_price
                skip_initial_stop_loss = (
                    not close_info.close_reason and PositionSide.N in close_info.strategy
                )
                sl_triggered = False
                if not skip_initial_stop_loss:
                    sl_triggered = (is_long and sl_ref_price <= close_info.stop_loss) or (
                        not is_long and sl_ref_price >= close_info.stop_loss
                    )
                # 止盈触发条件
                tp_triggered = (
                    is_long and current_price >= close_info.take_profit
                ) or (not is_long and current_price <= close_info.take_profit)

                if sl_triggered:  # 触及止损 - 全仓平仓
                    if not close_info.close_reason:
                        close_info.close_reason = "初始止损"
                    await self.close_bn_position(
                        symbol, close_info, atr_value, current_price, 1
                    )
                elif tp_triggered:  # 触及止盈 - 部分平仓
                    # 止盈次数+1，加速后续衰减
                    close_info.tp_count += 1
                    close_info.close_reason = "止盈"
                    await self.close_bn_position(
                        symbol,
                        close_info,
                        atr_value,
                        current_price,
                        self.PARTIAL_CLOSE_RATIO,
                    )

                else:
                    # 计算当前supertrend上下轨，用于止盈边界限制
                    hl2 = (kline[-1][2] + kline[-1][3]) / 2  # (high + low) / 2
                    current_upper = hl2 + atr_value * self.SUPERTREND_FACTOR  # 当前上轨
                    current_lower = hl2 - atr_value * self.SUPERTREND_FACTOR  # 当前下轨
                    # ATR触发阈值：用于收益阈值比较（与1/3预期收益取较小值）
                    atr_trigger = max(
                        min(
                            atr_value,
                            close_info.entry_price * self.ATR_TRIGGER_CAP_RATIO,
                        ),
                        self.MIN_ATR_TRIGGER,
                    )

                    if close_info.position_side.value == PositionSide.LONG.value:
                        if current_price < close_info.entry_price - atr_value:
                            if PositionSide.N not in close_info.strategy:
                                long_short_ratio_data = await self.get_long_short_ratio(
                                    symbol
                                )
                                latest_lsr = None
                                if long_short_ratio_data:
                                    try:
                                        latest_lsr = float(
                                            long_short_ratio_data[-1]["longShortRatio"]
                                        )
                                    except KeyError, TypeError, ValueError:
                                        latest_lsr = None
                                lsr_abnormal = (
                                    latest_lsr is not None
                                    and latest_lsr > self.DCA_LONG_SHORT_RATIO_THRESHOLD
                                )
                                if close_info.oi_guard_threshold <= 0:
                                    oi_1h = await self._get_oi_1h_data(symbol, dtn)
                                    if oi_1h:
                                        oi_1h_values = [
                                            float(item["sumOpenInterest"])
                                            for item in oi_1h
                                        ]
                                        if oi_1h_values:
                                            close_info.oi_guard_threshold = min(
                                                oi_1h_values
                                            )
                                oi_guard_failed = False
                                if close_info.oi_guard_threshold > 0:
                                    oi_5m = await self._get_oi_5m_data(symbol)
                                    oi_guard_failed = (
                                        oi_5m
                                        and float(oi_5m[-1]["sumOpenInterest"])
                                        < close_info.oi_guard_threshold
                                    )
                                if lsr_abnormal and oi_guard_failed:
                                    close_info.close_reason = "DCA多空比异常且OI不满足"
                                    await self.close_bn_position(
                                        symbol,
                                        close_info,
                                        atr_value,
                                        current_price,
                                        1,
                                    )
                                    return
                            close_info.strategy.append(PositionSide.DCA)
                            if await self.open_bn_position(
                                symbol,
                                OrderSide.BUY.value,
                                PositionSide.LONG.value,
                                close_info.take_profit,
                                close_info.stop_loss,  # 止损价用于计算风险仓位
                                close_info,
                            ):
                                amount_price = await self.get_amount_close(symbol)
                                close_info.entry_price = amount_price[1]
                                dca_count = sum(
                                    1
                                    for strategy in close_info.strategy
                                    if strategy == PositionSide.DCA
                                )
                                target_take_profit = (
                                    close_info.entry_price
                                    + self.DCA_TP_ATR_RATIO * atr_value * dca_count
                                )
                                close_info.take_profit = min(
                                    close_info.take_profit,
                                    target_take_profit,
                                )
                            else:
                                if (
                                    close_info.strategy
                                    and close_info.strategy[-1] == PositionSide.DCA
                                ):
                                    close_info.strategy.pop()
                        else:
                            # 做多: 基于入场价格计算初始距离，线性衰减
                            # 衰减系数 = 1 + tp_count (每次止盈后加速)
                            decay_multiplier = 1 + close_info.tp_count
                            initial_tp_gap = (
                                close_info.take_profit - close_info.entry_price
                            )  # 止盈到入场价的初始距离
                            tp_decay_step = (
                                initial_tp_gap
                                * self.STOP_LOSS_DECAY_PER_MINUTE
                                * decay_multiplier
                            )
                            # 止盈下移: 取衰减后的值和当前上轨的较大值（止盈不低于当前上轨）
                            decayed_tp = close_info.take_profit - tp_decay_step
                            close_info.take_profit = min(decayed_tp, current_upper)

                            if close_info.tp_count > 0:
                                profit = current_price - close_info.entry_price
                                trailing_stop = (
                                    close_info.entry_price
                                    + profit * self.TRAILING_STOP_PROFIT_RATIO
                                )
                                new_stop_loss = max(
                                    close_info.stop_loss,
                                    trailing_stop,
                                )
                                if new_stop_loss != close_info.stop_loss:
                                    close_info.stop_loss = new_stop_loss
                                    close_info.close_reason = "止盈后追踪止损"
                            else:
                                # 检测是否达到预期收益的1/3，如果是则设置止损为保护70%盈利
                                profit = current_price - close_info.entry_price
                                target_profit = min(
                                    initial_tp_gap / self.TARGET_PROFIT_DIVISOR,
                                    atr_trigger,
                                )  # 预期收益的1/3 与 ATR触发阈值取较小值
                                if profit >= target_profit:
                                    # 达到目标盈利，止损设置为当前盈利回撤30%的位置
                                    # 止损 = 入场价 + 盈利 * TRAILING_STOP_PROFIT_RATIO
                                    trailing_stop = (
                                        close_info.entry_price
                                        + profit * self.TRAILING_STOP_PROFIT_RATIO
                                    )
                                    new_stop_loss = max(
                                        close_info.stop_loss,
                                        trailing_stop,
                                    )
                                    if new_stop_loss != close_info.stop_loss:
                                        close_info.stop_loss = new_stop_loss
                                        close_info.close_reason = "追踪止损(保护盈利)"
                                else:
                                    # 止损上移: 使用当前下轨作为参考，止损只能上移（保护利润）
                                    # 取当前下轨和原止损的较大值
                                    new_stop_loss = max(
                                        close_info.stop_loss,
                                        current_lower,
                                    )
                                    if new_stop_loss != close_info.stop_loss:
                                        close_info.stop_loss = new_stop_loss
                                        close_info.close_reason = "移动止损(轨道)"

                    elif close_info.position_side.value == PositionSide.SHORT.value:
                        if current_price > close_info.entry_price + atr_value:
                            if PositionSide.N not in close_info.strategy:
                                long_short_ratio_data = await self.get_long_short_ratio(
                                    symbol
                                )
                                latest_lsr = None
                                if long_short_ratio_data:
                                    try:
                                        latest_lsr = float(
                                            long_short_ratio_data[-1]["longShortRatio"]
                                        )
                                    except KeyError, TypeError, ValueError:
                                        latest_lsr = None
                                if latest_lsr is not None and latest_lsr < (
                                    1 / self.DCA_LONG_SHORT_RATIO_THRESHOLD
                                ):
                                    close_info.close_reason = "DCA多空比异常"
                                    await self.close_bn_position(
                                        symbol, close_info, atr_value, current_price, 1
                                    )
                                    return
                            close_info.strategy.append(PositionSide.DCA)
                            if await self.open_bn_position(
                                symbol,
                                OrderSide.SELL.value,
                                PositionSide.SHORT.value,
                                close_info.take_profit,
                                close_info.stop_loss,  # 止损价用于计算风险仓位
                                close_info,
                            ):
                                amount_price = await self.get_amount_close(symbol)
                                close_info.entry_price = amount_price[1]
                                dca_count = sum(
                                    1
                                    for strategy in close_info.strategy
                                    if strategy == PositionSide.DCA
                                )
                                target_take_profit = (
                                    close_info.entry_price
                                    - self.DCA_TP_ATR_RATIO * atr_value * dca_count
                                )
                                close_info.take_profit = max(
                                    close_info.take_profit,
                                    target_take_profit,
                                )
                            else:
                                if (
                                    close_info.strategy
                                    and close_info.strategy[-1] == PositionSide.DCA
                                ):
                                    close_info.strategy.pop()
                        else:
                            # 做空: 止损在上界(stop_loss变量),止盈在下界(take_profit变量)
                            # 衰减系数 = 1 + tp_count (每次止盈后加速)
                            decay_multiplier = 1 + close_info.tp_count
                            initial_tp_gap = (
                                close_info.entry_price - close_info.take_profit
                            )  # 入场价到止盈的初始距离
                            tp_decay_step = (
                                initial_tp_gap
                                * self.STOP_LOSS_DECAY_PER_MINUTE
                                * decay_multiplier
                            )
                            # 止盈上移: 取衰减后的值和当前下轨的较小值（止盈不高于当前下轨）
                            decayed_tp = close_info.take_profit + tp_decay_step
                            close_info.take_profit = max(decayed_tp, current_lower)

                            if close_info.tp_count > 0:
                                profit = close_info.entry_price - current_price
                                trailing_stop = (
                                    close_info.entry_price
                                    - profit * self.TRAILING_STOP_PROFIT_RATIO
                                )
                                new_stop_loss = min(
                                    close_info.stop_loss,
                                    trailing_stop,
                                )
                                if new_stop_loss != close_info.stop_loss:
                                    close_info.stop_loss = new_stop_loss
                                    close_info.close_reason = "止盈后追踪止损"
                            else:
                                # 检测是否达到预期收益的1/3，如果是则设置止损为保护70%盈利
                                profit = close_info.entry_price - current_price
                                target_profit = min(
                                    initial_tp_gap / self.TARGET_PROFIT_DIVISOR,
                                    atr_trigger,
                                )  # 预期收益的1/3 与 ATR触发阈值取较小值
                                if profit >= target_profit:
                                    # 达到目标盈利，止损设置为当前盈利回撤30%的位置
                                    # 止损 = 入场价 - 盈利 * TRAILING_STOP_PROFIT_RATIO
                                    trailing_stop = (
                                        close_info.entry_price
                                        - profit * self.TRAILING_STOP_PROFIT_RATIO
                                    )
                                    new_stop_loss = min(
                                        close_info.stop_loss,
                                        trailing_stop,
                                    )
                                    if new_stop_loss != close_info.stop_loss:
                                        close_info.stop_loss = new_stop_loss
                                        close_info.close_reason = "追踪止损(保护盈利)"
                                else:
                                    # 止损下移: 使用当前上轨作为参考，止损只能下移（保护利润）
                                    # 取当前上轨和原止损的较小值
                                    new_stop_loss = min(
                                        close_info.stop_loss,
                                        current_upper,
                                    )
                                    if new_stop_loss != close_info.stop_loss:
                                        close_info.stop_loss = new_stop_loss
                                        close_info.close_reason = "移动止损(轨道)"

                    # 更新回字典
                    self.alert_all["POSITIONS"][symbol] = close_info.model_dump()
            elif open_info:
                if (
                    current_timestamp - open_info.timestamp
                    > self.OBSERVATION_TIMEOUT_SECONDS
                ):
                    self.alert_all["OBSERVATIONS"].pop(symbol)
                    open_info = None
                else:
                    should_open = False
                    atr_value = None
                    hl2 = None

                    long_ok, long_lsr, long_oi_guard_threshold = False, None, None
                    if (
                        PositionSide.BZ in open_info.strategy
                        and kline_close[-2] < current_price
                    ):
                        (
                            long_ok,
                            long_lsr,
                            long_oi_guard_threshold,
                        ) = await self.check_side(
                            semaphore,
                            symbol,
                            PositionSide.LONG.value,
                            kline_close,
                            dtn,
                        )
                    if long_ok:
                        # 在基差率判断前发送观察信号
                        hl2 = (kline[-1][2] + kline[-1][3]) / 2
                        atr_value = self.calculate_atr(kline)
                        zy_msg, zs_msg = self.calc_stop_profit_loss(
                            hl2,
                            is_long=True,
                            atr=atr_value,
                        )
                        if not (zy_msg == 0 and zs_msg == 0):
                            basis_rate = await self.get_basis_rate(symbol)
                            if basis_rate < -self.BASIS_RATE_THRESHOLD:
                                open_info.strategy.append(PositionSide.Basis)
                            lsr_show = (
                                f"{long_lsr:.4f}" if long_lsr is not None else "N/A"
                            )
                            rate_show = (
                                atr_value * self.SUPERTREND_FACTOR / current_price
                            )
                            await self.send_msg(
                                f"==={symbol}**{','.join([ps.value for ps in open_info.strategy])}**===\n价格:{current_price}\n基差率:{basis_rate:.4%}\n多空比:{lsr_show}\n止盈:{zy_msg}\n止损:{zs_msg}\n收益率:{rate_show:.2%}",
                                qy_key=self.signal_qy_key,
                            )
                            await self.send_msg(
                                f"==={symbol}**{','.join([ps.value for ps in open_info.strategy])}**===\n价格:{current_price}\n基差率:{basis_rate:.4%}\n多空比:{lsr_show}\n止盈:{zy_msg}\n止损:{zs_msg}\n收益率:{rate_show:.2%}"
                            )
                            open_info.side = OrderSide.BUY
                            should_open = True
                    short_ok, short_lsr, _ = False, None, None
                    if (
                        not long_ok
                        and PositionSide.BD in open_info.strategy
                        and current_price < kline_close[-2]
                    ):
                        short_ok, short_lsr, _ = await self.check_side(
                            semaphore,
                            symbol,
                            PositionSide.SHORT.value,
                            kline_close,
                            dtn,
                        )
                    if short_ok:
                        # 在基差率判断前发送观察信号
                        hl2 = (kline[-1][2] + kline[-1][3]) / 2
                        atr_value = self.calculate_atr(kline)
                        zy_msg, zs_msg = self.calc_stop_profit_loss(
                            hl2,
                            is_long=False,
                            atr=atr_value,
                        )
                        if not (zy_msg == 0 and zs_msg == 0):
                            basis_rate = await self.get_basis_rate(symbol)
                            if basis_rate > self.BASIS_RATE_THRESHOLD:
                                open_info.strategy.append(PositionSide.Basis)
                            lsr_show = (
                                f"{short_lsr:.4f}" if short_lsr is not None else "N/A"
                            )
                            rate_show = (
                                atr_value * self.SUPERTREND_FACTOR / current_price
                            )
                            await self.send_msg(
                                f"==={symbol}**{','.join([ps.value for ps in open_info.strategy])}**===\n价格:{current_price}\n基差率:{basis_rate:.4%}\n多空比:{lsr_show}\n止盈:{zy_msg}\n止损:{zs_msg}\n收益率:{rate_show:.2%}",
                                qy_key=self.signal_qy_key,
                            )
                            await self.send_msg(
                                f"==={symbol}**{','.join([ps.value for ps in open_info.strategy])}**===\n价格:{current_price}\n基差率:{basis_rate:.4%}\n多空比:{lsr_show}\n止盈:{zy_msg}\n止损:{zs_msg}\n收益率:{rate_show:.2%}"
                            )
                            open_info.side = OrderSide.SELL
                            should_open = True
                    if should_open:
                        last_close_ts = (
                            self.alert_all.get("CLOSE_TS", {}).get(symbol, 0) or 0
                        )
                        if (
                            current_timestamp - float(last_close_ts)
                            < self.REOPEN_COOLDOWN_SECONDS
                        ):
                            self.logger.info(f"{symbol} 24小时内已平仓，跳过开仓信号")
                            return
                        is_long = open_info.side.value == OrderSide.BUY.value
                        if atr_value is None or hl2 is None:
                            # 兜底：确保后续止盈止损计算可用
                            hl2 = (kline[-1][2] + kline[-1][3]) / 2
                            atr_value = self.calculate_atr(kline)
                        zy, zs = self.calc_stop_profit_loss(
                            hl2, is_long=is_long, atr=atr_value
                        )
                        if zy == 0 and zs == 0:
                            return

                        position_side = (
                            PositionSide.LONG if is_long else PositionSide.SHORT
                        )
                        await self.open_bn_position(
                            symbol,
                            OrderSide.BUY.value if is_long else OrderSide.SELL.value,
                            position_side.value,
                            zy,
                            zs,  # 止损价用于计算风险仓位
                            open_info,
                        )
                        # 多头: zy=高价(止盈), zs=低价(止损)
                        # 空头: zy=低价(止盈), zs=高价(止损)
                        close_info = Position(
                            take_profit=zy,  # 多头高价止盈，空头低价止盈
                            stop_loss=zs,  # 多头低价止损，空头高价止损
                            close_side=OrderSide.SELL if is_long else OrderSide.BUY,
                            position_side=position_side,
                            entry_price=current_price,
                            name=symbol,
                            date=int(dtn.strftime("%Y%m%d")),
                            strategy=open_info.strategy,
                            oi_guard_threshold=(
                                long_oi_guard_threshold
                                if is_long and long_oi_guard_threshold is not None
                                else 0.0
                            ),
                        )
                        self.alert_all["POSITIONS"][symbol] = close_info.model_dump()
                        open_info.strategy = [open_info.strategy[0]]
                        # 更新timestamp为当前时间，确保同一天(UTC)内不会再次触发Supertrend开仓
                        open_info.timestamp = current_timestamp
                        self.alert_all["OBSERVATIONS"][symbol] = open_info.model_dump()

            # 无论是否有仓位，都执行“加入观察”判定逻辑；同一UTC日仅记录一次，避免重复告警
            can_set_observation = True
            if open_info:
                observation_date = datetime.datetime.fromtimestamp(
                    open_info.timestamp, datetime.timezone.utc
                ).date()
                current_date = datetime.datetime.fromtimestamp(
                    current_timestamp, datetime.timezone.utc
                ).date()
                can_set_observation = observation_date != current_date

            if can_set_observation:
                new_open_info = None

                # 做多信号判断
                if kline_close[-2] < current_price and kline_volume[-1] >= max(
                    kline_volume[-self.VOLUME_LOOKBACK_PERIOD :]
                ):
                    new_open_info = Observation(
                        price=current_price,
                        timestamp=current_timestamp,
                        side=OrderSide.BUY,
                        strategy=[PositionSide.BZ],
                        name=symbol,
                    )

                # 做空信号判断
                elif max(kline_close[-3:]) >= max(kline_close) and max(
                    kline_volume[-3:]
                ) >= max(kline_volume):
                    new_open_info = Observation(
                        price=current_price,
                        timestamp=current_timestamp,
                        side=OrderSide.SELL,
                        strategy=[PositionSide.BD],
                        name=symbol,
                    )
                if new_open_info:
                    self.alert_all["OBSERVATIONS"][symbol] = new_open_info.model_dump()
        except Exception:
            self.logger.exception("处理持仓信息时发生异常")
            return

    def get_symbols_info(self, exchange_info=None):
        # 获取交易所信息（公开合约元信息使用 USDS-M Futures 新 SDK）
        if exchange_info is None:
            exchange_info = self.market_client.rest_api.exchange_information()

        # 计算数量精度：根据quantityPrecision生成对应的Decimal精度
        sp = {
            i["symbol"]: Decimal("1")
            if i["quantityPrecision"] == 0
            else Decimal(f"0.{'1' * i['quantityPrecision']}")
            for i in exchange_info["symbols"]
        }

        # 筛选USDT交易对：只处理USDT计价且状态为TRADING的交易对
        self.symbols_info = {
            symbol["symbol"]: {
                "quotePrecision": symbol["quotePrecision"],  # 价格精度
                # 数量精度
                "quantityPrecision": sp.get(symbol["symbol"], Decimal("1")),
            }
            for symbol in exchange_info["symbols"]
            if "USDT" in symbol["quoteAsset"] and "TRADING" in symbol["status"]
        }

    def get_position_risk(self, position_risk=None):
        # 获取当前持仓信息，用于清理无效持仓
        position_risk = self._normalize_position_risk(position_risk)
        position_risk_symbol = [i["symbol"] for i in position_risk]
        # 只保留当前有持仓的交易对记录
        self.alert_all["POSITIONS"] = {
            k: v
            for k, v in self.alert_all["POSITIONS"].items()
            if k in position_risk_symbol
        }
        positions_data = []
        for p in position_risk:
            entryPrice = float(p["entryPrice"])
            notional = abs(float(p.get("notional", 0) or 0))
            unrealized_profit = float(p.get("unRealizedProfit", 0) or 0)
            if notional == 0:
                self.logger.info(
                    f"跳过名义价值为0的持仓记录: symbol={p.get('symbol')} side={p.get('positionSide')}"
                )
                continue
            strategy_tag = ""
            if p["symbol"] in self.alert_all["POSITIONS"]:
                pos_data = self.alert_all["POSITIONS"][p["symbol"]]
                if isinstance(pos_data, dict) and "strategy" in pos_data:
                    strategy_list = pos_data["strategy"]
                    strategy_tag = ",".join(strategy_list) if strategy_list else ""
            positions_data.append(
                f"==={p['symbol']}===\n策略:{strategy_tag}\n开仓价格:{entryPrice} USDT\n持仓方向:{p['positionSide']}\n名义价值:{p['notional']} USDT\n持仓盈亏:{p['unRealizedProfit']} USDT\n持仓收益:{unrealized_profit / notional:.2%}"
            )

            if p["symbol"] not in self.alert_all["POSITIONS"]:
                if p["positionSide"] == PositionSide.LONG.value:
                    close_info = Position(
                        take_profit=0,
                        stop_loss=0,
                        close_side=OrderSide.SELL,
                        position_side=PositionSide.LONG,
                        entry_price=entryPrice,
                        name=p["symbol"],
                        date=int(datetime.datetime.now().strftime("%Y%m%d")),
                        strategy=[PositionSide.N],
                    )
                    self.alert_all["POSITIONS"][p["symbol"]] = close_info.model_dump()
                else:
                    close_info = Position(
                        take_profit=0,
                        stop_loss=0,
                        close_side=OrderSide.BUY,
                        position_side=PositionSide.SHORT,
                        entry_price=entryPrice,
                        name=p["symbol"],
                        date=int(datetime.datetime.now().strftime("%Y%m%d")),
                        strategy=[PositionSide.N],
                    )
                    self.alert_all["POSITIONS"][p["symbol"]] = close_info.model_dump()
            else:
                current_pos_list = self.alert_all["POSITIONS"][p["symbol"]]
                pos_obj = Position.model_validate(current_pos_list)
                pos_obj.entry_price = entryPrice
                self.alert_all["POSITIONS"][p["symbol"]] = pos_obj.model_dump()

        return "\n\n".join(positions_data) if positions_data else "暂无持仓"

    async def rzq_market(self, market):
        """
        市场分析主函数：获取交易对信息并批量处理

        功能：这是整个交易系统的入口函数，负责：
        1. 获取所有可交易的USDT交易对
        2. 清理无效的持仓记录
        3. 批量分析所有交易对
        4. 保存分析结果

        参数：
            market: 市场名称，如'BN'（币安）
        """
        try:
            # 设置超时时间为5分钟，防止任务卡住
            self.logger.info(f"{market} 市场分析任务开始")
            await asyncio.wait_for(
                self._rzq_market_impl(market), timeout=self.MARKET_ANALYSIS_TIMEOUT
            )
        except asyncio.TimeoutError:
            error_msg = (
                f"{market} 市场分析任务超时({self.MARKET_ANALYSIS_TIMEOUT}秒)，已强制中断"
            )
            self.logger.error(error_msg)
            await self.send_msg(error_msg)
        except Exception as e:
            error_msg = f"{market} 市场分析任务异常: {str(e)}"
            self.logger.error(error_msg)
            self.logger.exception("市场分析任务发生异常")
            await self.send_msg(error_msg)

    async def _rzq_market_impl(self, market):
        """市场分析的实际实现"""
        now = datetime.datetime.now()
        self.is_early_morning = now.hour == self.EARLY_MORNING_HOUR and now.minute == 0

        # 重试机制：最多尝试10次获取交易对信息
        if now.minute % 15 == 0 or not self.symbols:
            for i in range(self.MAX_RETRY_COUNT):
                try:
                    position_risk_data = await self._call_api(
                        self.papi_client.rest_api.query_um_position_information
                    )
                    positions_data = self.get_position_risk(position_risk_data)
                    exchange_info = await self._call_api(
                        self.market_client.rest_api.exchange_information
                    )
                    self.get_symbols_info(exchange_info)
                    self.symbols = list(self.symbols_info.keys())
                    break
                except Exception:
                    self.logger.exception("获取交易对信息时发生异常")
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)
        if self.is_early_morning:
            balance_info = await self._call_api(
                self.papi_client.rest_api.account_information
            )
            balance_info = self._normalize_account_info(balance_info)
            balance = balance_info["totalWalletBalance"]
            await self.send_msg(f"账户余额:\n{balance} USDT\n持仓信息:\n{positions_data}")
            self.logger.info("账户信息推送任务执行完成")

            def _write_alert_all_sync():
                with open(self.alert_all_file, "w", encoding="utf-8") as f:
                    json.dump(self.alert_all, f, ensure_ascii=False, indent=4)

            await asyncio.wait_for(
                asyncio.to_thread(_write_alert_all_sync),
                timeout=self.FILE_IO_TIMEOUT_SECONDS,
            )
        # 创建信号量，限制最大并发数，避免API限制
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

        # 5分钟窗口分批：每分钟仅处理一个slot，降低单分钟请求量
        window_seconds = self.BATCH_WINDOW_MINUTES * 60
        window_id = int(now.timestamp() // window_seconds)
        slot = now.minute % self.BATCH_SLOT_COUNT

        # 新窗口时冻结symbols快照，确保窗口内分片稳定
        if self._batch_window_id != window_id:
            self._batch_window_id = window_id
            self._batch_symbols_snapshot = sorted(self.symbols)

        snapshot_symbols = self._batch_symbols_snapshot
        batch_symbols = [
            symbol
            for index, symbol in enumerate(snapshot_symbols)
            if index % self.BATCH_SLOT_COUNT == slot
        ]
        position_symbols = list(self.alert_all["POSITIONS"].keys())
        effective_symbols = list(dict.fromkeys(batch_symbols + position_symbols))

        self.logger.info(
            f"{market}任务开始 - window:{window_id} slot:{slot}/{self.BATCH_SLOT_COUNT} "
            f"快照数量:{len(snapshot_symbols)} 批次数量:{len(batch_symbols)} "
            f"持仓数量:{len(position_symbols)} 实际处理数量:{len(effective_symbols)}"
        )

        success = set()  # 记录成功处理的交易对
        tasks = [
            self.rzq_token(semaphore, symbol, success, now)
            for symbol in effective_symbols
        ]

        # 等待当前批次任务完成
        if tasks:
            await asyncio.gather(*tasks)

        # 打印任务完成信息
        self.logger.info(
            f"{market}任务结束 - window:{window_id} slot:{slot}/{self.BATCH_SLOT_COUNT} "
            f"批次成功数量:{len(success)}"
        )


class AUTOA:
    # ==================== ATR风控常量 ====================
    ATR_PERIOD = 10  # ATR计算周期
    ATR_TRIGGER_CAP_RATIO = 0.10
    ATR_HL2_CAP_RATIO = 0.1  # ATR返回值上限比例（不超过hl2的10%）
    MIN_ATR_TRIGGER = 1e-8
    DCA_TP_ATR_RATIO = 0.5  # DCA触发后止盈收紧系数(按ATR与触发次数)

    # ==================== 切比雪夫概率阈值常量 ====================
    CHEBYSHEV_EXTREME_THRESHOLD = 0.01  # 极端异常阈值（5%），用于检测非常罕见的事件

    # ==================== 时间常量 ====================
    OBSERVATION_TIMEOUT_SECONDS = 30 * 24 * 60 * 60  # 观察记录超时时间（30天）

    # ==================== Supertrend Constants ====================
    SUPERTREND_FACTOR = 3.0

    # ==================== Trading Configuration ====================
    TRADING_DAYS_LOOKBACK = 60
    STOP_LOSS_DECAY = 0.001  # 止损衰减系数 (1‰)
    TRAILING_STOP_PROFIT_RATIO = 0.7  # 追踪止损盈利保护比例 (保护70%盈利，允许30%回撤)
    MARKET_OPEN_HOUR = 9  # A股开盘小时
    MARKET_OPEN_MINUTE = 30  # A股开盘分钟
    MARKET_CLOSE_HOUR = 15  # A股收盘小时
    MARKET_CLOSE_MINUTE = 5  # A股收盘分钟
    MONITOR_TIMEOUT = 55  # 股票监控任务总超时时间（秒）
    BATCH_WINDOW_MINUTES = 5  # 分批窗口时长（分钟）
    BATCH_SLOT_COUNT = 5  # 窗口内批次数（每分钟一批）
    MAX_CONCURRENT_REQUESTS = 8  # 最大并发请求数
    HTTP_TIMEOUT_SECONDS = 10  # HTTP请求超时时间（秒）
    FILE_IO_TIMEOUT_SECONDS = 10  # 文件IO超时时间（秒）
    AKSHARE_TIMEOUT_SECONDS = 15  # akshare请求超时时间（秒）
    BAOSTOCK_TIMEOUT_SECONDS = 15  # baostock请求超时时间（秒）

    # ==================== 均线与筛选常量 ====================
    MA_PERIOD = 10  # 均线周期
    BREAK_MA_LOOKBACK_DAYS = 5  # 跌破均线检查天数
    DEFAULT_POSITION_SHARES = 100  # 假设持仓股数（用于盈亏计算）
    VOLUME_CHEB_SAMPLE_START_OFFSET = -20  # 成交量切比雪夫样本窗口起点（含）
    VOLUME_CHEB_SAMPLE_END_OFFSET = -10  # 成交量切比雪夫样本窗口终点（不含）
    VOLUME_CHEB_REQUIRED_HISTORY = 20  # 切片[-20:-10]所需最少历史K线数
    TARGET_PROFIT_DIVISOR = 3.0  # 目标收益分割系数（用于计算1/3收益触发点）

    qy_key = "6f2ec864-c474-4c8f-b069-1e3c35eb7d73"
    alert_all_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "alert_all_A.json"
    )
    alert_all = json.load(open(alert_all_file, "r", encoding="utf-8"))
    zt_dates = []
    hist_cache = {}
    _batch_window_id = None
    _batch_observations_snapshot = []
    _http_session = None
    # 添加线程锁以保护 baostock 查询操作(baostock 不是线程安全的)
    _bs_lock = threading.Lock()
    logger = logging.getLogger("AUTOA")
    logger.setLevel(logging.INFO)  # 默认级别
    logger.propagate = False  # 防止日志向上层传播导致重复
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # 退出处理函数,在脚本退出时保存A股数据
    @staticmethod
    def _save_alert_all_on_exit():
        """脚本退出时保存AUTOA的alert_all数据到文件"""
        try:
            AUTOA.logger.info(f"脚本退出,正在保存AUTOA数据到 {AUTOA.alert_all_file}...")
            with open(AUTOA.alert_all_file, "w", encoding="utf-8") as f:
                json.dump(AUTOA.alert_all, f, ensure_ascii=False, indent=4)
            AUTOA.logger.info("AUTOA数据保存完成")
        except Exception as e:
            AUTOA.logger.error(f"保存AUTOA数据失败: {str(e)}")
            AUTOA.logger.exception("保存AUTOA数据时发生异常")

    @classmethod
    def calculate_atr(cls, hist_data, period=None):
        """
        计算ATR (平均真实波幅)
        :param hist_data: DataFrame, 包含 high, low, close 列
        """
        if period is None:
            period = cls.ATR_PERIOD
        if hist_data.empty or len(hist_data) < period + 1:
            return 0.0

        tr_list = []
        # 转换为列表处理以提高性能
        highs = hist_data["high"].values
        lows = hist_data["low"].values
        closes = hist_data["close"].values

        for i in range(1, len(hist_data)):
            h = float(highs[i])
            low_price = float(lows[i])
            pc = float(closes[i - 1])

            tr = max(h - low_price, abs(h - pc), abs(low_price - pc))
            tr_list.append(tr)

        if not tr_list:
            return 0.0
        atr = sum(tr_list[-period:]) / min(len(tr_list), period)
        latest_high = float(hist_data.iloc[-1]["high"])
        latest_low = float(hist_data.iloc[-1]["low"])
        hl2 = (latest_high + latest_low) / 2
        atr_cap = hl2 * cls.ATR_HL2_CAP_RATIO
        return min(atr, atr_cap) if atr_cap > 0 else atr

    @classmethod
    def check_gap_up_after_break_ma10(cls, hist: pd.DataFrame) -> bool:
        """
        检查是否满足"10日线下跳空高开"

        条件：
        1. 前两根K线（不含今天）收盘都在10日均线下方
        2. 今天跳空高开（开盘价 > 昨日最高价）

        参数:
            hist: K线数据DataFrame，需包含 open, high, close 列
        返回:
            bool: 是否满足条件
        """
        if len(hist) < cls.MA_PERIOD + 2:
            return False

        # 计算10日均线
        ma10 = hist["close"].rolling(window=cls.MA_PERIOD).mean()

        # 检查前两根K线（不含今天）是否都收盘在10日均线下方
        # 即 hist.iloc[-2] 和 hist.iloc[-3] 的收盘价都 < 10日均线
        yesterday_below_ma10 = pd.notna(ma10.iloc[-2]) and float(
            hist.iloc[-2]["close"]
        ) < float(ma10.iloc[-2])
        day_before_below_ma10 = pd.notna(ma10.iloc[-3]) and float(
            hist.iloc[-3]["close"]
        ) < float(ma10.iloc[-3])

        if not (yesterday_below_ma10 and day_before_below_ma10):
            return False

        # 今天跳空高开：开盘价 > 昨日最高价
        today_open = float(hist.iloc[-1]["open"])
        yesterday_high = float(hist.iloc[-2]["high"])

        return today_open > yesterday_high

    @classmethod
    def calculate_chebyshev_probability(cls, data, value):
        """
        计算给定数值对应的切比雪夫概率 (支持 pandas Series/DataFrame 和 list)

        功能：根据切比雪夫不等式计算给定数值在数据分布中的概率特征

        切比雪夫不等式：P(|X - μ| >= kσ) <= 1/k²
        换言之：至少有 (1 - 1/k²) 的数据落在 [μ - kσ, μ + kσ] 区间内

        参数：
            data: 数据集合，可以是 pandas.Series, pandas.DataFrame (单列) 或 list
            value: 给定的数值，用于计算其在分布中的位置

        返回：
            字典，包含以下信息：
            - mean: 数据均值
            - std: 数据标准差
            - k: 给定数值距离均值的标准差倍数
            - chebyshev_upper_bound: 切比雪夫不等式的上界概率 (1/k²)
            - min_probability_in_range: 至少有该比例的数据在 k 个标准差范围内 (1 - 1/k²)
            - deviation: 给定数值与均值的偏差
        """
        # 统一转换为 pandas Series 处理
        if isinstance(data, list):
            series = pd.Series(data)
        elif isinstance(data, pd.DataFrame):
            if data.shape[1] != 1:
                # 如果是多列 DataFrame，尝试取第一列，或者抛出异常
                # 这里假设用户传入的是单列数据
                series = data.iloc[:, 0]
            else:
                series = data.iloc[:, 0]
        elif isinstance(data, pd.Series):
            series = data
        else:
            # 尝试转换其他可迭代对象
            try:
                series = pd.Series(data)
            except Exception:
                raise ValueError(
                    "不支持的数据类型，请提供 list, pandas.Series 或 pandas.DataFrame"
                )

        # 输入验证
        if series.empty:
            raise ValueError("数据不能为空")

        # 处理单元素情况
        if len(series) == 1:
            item = float(series.iloc[0])
            return {
                "mean": item,
                "std": 0.0,
                "k": float("inf") if item != value else 0.0,
                "chebyshev_upper_bound": 0.0,
                "min_probability_in_range": 1.0,
                "deviation": value - item,
                "message": "数据只有一个元素，标准差为0",
            }

        # 利用 pandas 向量化计算均值和标准差
        mean = float(series.mean())
        std = float(series.std(ddof=1))  # 样本标准差

        # 计算给定数值与均值的偏差
        deviation = value - mean

        # 如果标准差为0（所有数据相同）
        if std == 0:
            return {
                "mean": mean,
                "std": 0.0,
                "k": float("inf") if deviation != 0 else 0.0,
                "chebyshev_upper_bound": 0.0,
                "min_probability_in_range": 1.0,
                "deviation": deviation,
                "message": "所有数据相同，标准差为0",
            }

        # 计算 k 值（给定数值距离均值有多少个标准差）
        k = abs(deviation) / std

        # 切比雪夫不等式的上界：P(|X - μ| >= kσ) <= 1/k²
        # 只有当 k > 1 时，切比雪夫不等式才有意义
        if k <= 1:
            chebyshev_upper_bound = 1.0  # k <= 1 时，不等式给出的上界为 1（无信息）
            min_probability_in_range = 0.0
        else:
            chebyshev_upper_bound = 1 / (k**2)
            # 至少有 (1 - 1/k²) 的数据落在 [μ - kσ, μ + kσ] 区间内
            min_probability_in_range = 1 - chebyshev_upper_bound

        result = {
            "mean": mean,
            "std": std,
            "k": k,
            "chebyshev_upper_bound": chebyshev_upper_bound,
            "min_probability_in_range": min_probability_in_range,
            "deviation": deviation,
        }

        # 添加人类可读的解释
        if k <= 1:
            result["message"] = (
                f"数值 {value:.4f} 距离均值 {mean:.4f} 只有 {k:.4f} 个标准差（在 1σ 范围内），切比雪夫不等式不提供有用信息"
            )
        else:
            result["message"] = (
                f"数值 {value:.4f} 距离均值 {mean:.4f} 约 {k:.4f} 个标准差。"
                f"根据切比雪夫不等式，至少有 {min_probability_in_range:.2%} 的数据"
                f"落在 [μ - {k:.4f}σ, μ + {k:.4f}σ] 范围内，"
                f"即 [{mean - k * std:.4f}, {mean + k * std:.4f}] 区间。"
                f"超出此范围的数据比例不超过 {chebyshev_upper_bound:.2%}。"
            )

        return result

    @classmethod
    async def _get_http_session(cls):
        if cls._http_session is None or cls._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=cls.HTTP_TIMEOUT_SECONDS)
            cls._http_session = aiohttp.ClientSession(timeout=timeout)
        return cls._http_session

    @classmethod
    async def send_msg(cls, msg):
        """
        发送消息通知函数

        功能：通过企业微信发送交易通知消息
        参数：
            msg: 要发送的消息内容
        """
        try:
            cls.logger.info(f"发送消息: {msg}")
            json_msg = {"msgtype": "text", "text": {"content": msg}}
            http_session = await cls._get_http_session()
            async with http_session.post(
                url=f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={cls.qy_key}",
                json=json_msg,
            ) as response:
                if response.status != 200:
                    cls.logger.error(f"消息发送失败，状态码: {response.status}")
        except Exception as e:
            cls.logger.error(f"消息发送异常: {str(e)}")

    @classmethod
    async def push_daily_positions(cls):
        """每日推送一次A股持仓信息（模板参考AUTOBN）"""
        try:
            positions = cls.alert_all.get("POSITIONS", {})
            if not positions:
                await cls.send_msg("账户余额:\nN/A\n持仓信息:\n暂无持仓")
                return

            positions_data = []
            for code, close_info_dict in positions.items():
                close_info = Position.model_validate(close_info_dict)
                strategy_tag = ",".join([ps.value for ps in close_info.strategy])
                positions_data.append(
                    f"==={close_info.name}({code})===\n"
                    f"策略:{strategy_tag}\n"
                    f"开仓价格:{close_info.entry_price:.2f} CNY\n"
                    f"持仓方向:{close_info.position_side.value}\n"
                    f"止盈:{close_info.take_profit:.2f}\n"
                    f"止损:{close_info.stop_loss:.2f}\n"
                    f"开仓日期:{close_info.date}"
                )

            await cls.send_msg("账户余额:\nN/A\n持仓信息:\n" + "\n\n".join(positions_data))
        except Exception:
            cls.logger.exception("A股每日持仓推送失败")

    @staticmethod
    async def get_last_trading_days(today=None, days=None):
        """
        获取A股交易日历

        功能：从新浪财经获取A股交易日历，用于股票筛选
        参数：
            today: 指定日期，默认为当前日期
            days: 获取最近交易日的天数，默认为 TRADING_DAYS_LOOKBACK
        返回：
            交易日期字符串列表（按时间降序排列）
        """
        # 设置默认日期为今天
        if not today:
            today = datetime.datetime.today()

        if days is None:
            days = AUTOA.TRADING_DAYS_LOOKBACK

        try:
            # 从新浪财经获取交易日历
            trade_dates = await asyncio.wait_for(
                asyncio.to_thread(ak.tool_trade_date_hist_sina),
                timeout=AUTOA.AKSHARE_TIMEOUT_SECONDS,
            )
            trade_dates = pd.to_datetime(trade_dates["trade_date"])

            # 过滤出不晚于指定日期的交易日
            valid_dates = trade_dates[trade_dates <= today]

            if valid_dates.empty:
                AUTOA.logger.warning(f"未找到 {today} 之前的交易日")
                return []

            # 获取指定日期前的最近n个交易日，按时间降序排列
            recent_trading_days = valid_dates.sort_values(ascending=False).iloc[:days]

            # 选择第3天到第10天的交易日作为涨停股查询日期（避开最近的波动）
            return [i.strftime("%Y-%m-%d") for i in recent_trading_days.iloc]
        except Exception as e:
            AUTOA.logger.error(f"获取交易日历失败: {str(e)}")
            return []

    @classmethod
    async def stock_zh_a_hist(
        cls,
        code,
        fields="date,code,open,high,low,close,preclose,volume,amount",
        start_date=None,
        end_date=None,
        frequency="d",
        adjustflag="3",
    ):
        try:
            code_pre = "sh" if code[0] == "6" else "sz"
            cls.logger.debug(f"stock_zh_a_hist 调用: code={code}, code_pre={code_pre}")
            if code in cls.hist_cache:
                data_list = copy.deepcopy(cls.hist_cache[code])
                cls.logger.debug(
                    f"从缓存读取 code={code}, data_list前3行={data_list[:3] if data_list else 'empty'}"
                )
            else:

                def fetch_bs_data(
                    stock_code_pre,
                    stock_code,
                    flds,
                    s_date,
                    e_date,
                    freq,
                    adj_flag,
                    lock,
                ):
                    cls.logger.debug(
                        f"fetch_bs_data 开始获取: {stock_code_pre}.{stock_code}"
                    )
                    # 使用线程锁保护 baostock 查询（baostock 不是线程安全的）
                    with lock:
                        rs = bs.query_history_k_data_plus(
                            f"{stock_code_pre}.{stock_code}",  # 股票代码
                            flds,
                            start_date=s_date,
                            end_date=e_date,
                            frequency=freq,  # 日K
                            adjustflag=adj_flag,  # 3：前复权；1：不复权；2：后复权
                        )
                        dl = []
                        while (rs.error_code == "0") & rs.next():
                            dl.append(rs.get_row_data())

                    # 验证返回的数据
                    if dl and len(dl[0]) > 1:
                        actual_code = dl[0][1]
                        expected_code = f"{stock_code_pre}.{stock_code}"
                        if actual_code != expected_code:
                            cls.logger.error(
                                f"数据错误! 请求={expected_code}, 实际={actual_code}"
                            )

                    cls.logger.debug(
                        f"fetch_bs_data 完成获取: {stock_code_pre}.{stock_code}, 数据行数={len(dl)}"
                    )
                    return dl

                data_list = await asyncio.wait_for(
                    asyncio.to_thread(
                        fetch_bs_data,
                        code_pre,
                        code,
                        fields,
                        start_date,
                        end_date,
                        frequency,
                        adjustflag,
                        cls._bs_lock,
                    ),
                    timeout=cls.BAOSTOCK_TIMEOUT_SECONDS,
                )
                if data_list:
                    # 检查data_list中的股票代码
                    actual_code_in_data = (
                        data_list[0][1]
                        if data_list and len(data_list[0]) > 1
                        else "unknown"
                    )
                    cls.logger.debug(
                        f"准备写入缓存 code={code}, data_list中的股票代码={actual_code_in_data}, 数据行数={len(data_list)}"
                    )
                    cls.hist_cache[code] = copy.deepcopy(data_list)
            if not data_list:
                return pd.DataFrame()

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://finance.sina.com.cn/",
            }
            res = []
            try:
                http_session = await cls._get_http_session()
                async with http_session.get(
                    url=f"https://cn.finance.sina.com.cn/minline/getMinlineData?symbol={code_pre}{code}",
                    headers=headers,
                ) as response:
                    payload = await response.json(content_type=None)
                    res = payload.get("result", {}).get("data", [])
            except Exception:
                pass
            if not res:
                return pd.DataFrame()
            hist_today = pd.DataFrame(res, columns=["m", "v", "p", "avg_p"])
            hist_today["v"] = pd.to_numeric(hist_today["v"], errors="coerce")
            volume = hist_today["v"].sum()
            data_list.append(
                [
                    end_date,
                    f"{code_pre}.{code}",
                    res[0]["p"],
                    res[-1]["p"],
                    res[0]["p"],
                    res[-1]["p"],
                    data_list[-1][5],
                    volume,
                    0,
                ]
            )
            hist = pd.DataFrame(data_list, columns=fields.split(","))
            hist["open"] = pd.to_numeric(hist["open"], errors="coerce")
            hist["high"] = pd.to_numeric(hist["high"], errors="coerce")
            hist["low"] = pd.to_numeric(hist["low"], errors="coerce")
            hist["close"] = pd.to_numeric(hist["close"], errors="coerce")
            hist["volume"] = pd.to_numeric(hist["volume"], errors="coerce")
            hist["preclose"] = pd.to_numeric(hist["preclose"], errors="coerce")
            hist["涨跌幅"] = (hist["close"] - hist["preclose"]) / hist["preclose"]
            return hist
        except Exception:
            cls.logger.exception("获取股票历史数据时发生异常")
            return pd.DataFrame()

    @classmethod
    async def on_positions(cls, code, zt_dates, close_info_dict, today):
        """
        处理持仓列表中的股票，检测平仓信号

        策略：止盈止损 - 当价格触及止盈或止损线时平仓，成功后记录到Excel
        核心逻辑：
            - 止盈触发：当前价 >= 止盈价
            - 止损触发：当前价 <= 止损价
            - 触发后将股票移至观察列表（非BZ策略会发送通知）

        参数：
            code: 股票代码（如'000001'）
            zt_dates: 交易日期列表
            close_info_dict: 持仓记录字典 (Pydantic Position.model_dump())
            today: 当前日期时间
        """
        close_info = Position.model_validate(close_info_dict)
        if int(today.strftime("%Y%m%d")) <= close_info.date:
            return
        # 获取股票历史数据（前复权）
        hist = await cls.stock_zh_a_hist(
            code,
            "date,code,open,high,low,close,preclose,volume,amount",
            start_date=zt_dates[-1],
            end_date=zt_dates[0],
            frequency="d",  # 日K
            adjustflag="3",  # 前复权
        )

        # 数据校验
        if hist.empty:
            return

        # 获取最新价格
        price_close = float(hist.iloc[-1]["close"])

        # 检查是否触及止盈或止损（且已持仓至少1天）
        prev_close = float(hist.iloc[-2]["close"]) if len(hist) > 1 else price_close
        skip_initial_stop_loss = (
            not close_info.close_reason and PositionSide.N in close_info.strategy
        )
        stop_loss_triggered = price_close <= close_info.stop_loss
        if not close_info.close_reason and not skip_initial_stop_loss:
            stop_loss_triggered = (
                price_close <= close_info.stop_loss
                and prev_close <= close_info.stop_loss
            )
        if stop_loss_triggered or price_close >= close_info.take_profit:
            if price_close >= close_info.take_profit:
                close_info.close_reason = "止盈"
            else:
                if not close_info.close_reason:
                    close_info.close_reason = "初始止损"
            # 从持仓列表移除
            cls.alert_all["POSITIONS"].pop(code)

            # 发送平仓通知
            entry_price = (
                close_info.entry_price if close_info.entry_price > 0 else price_close
            )
            profit_rate = (price_close / entry_price - 1) if entry_price > 0 else 0
            realized_pnl = (price_close - entry_price) * cls.DEFAULT_POSITION_SHARES
            strategy_tag = ",".join([ps.value for ps in close_info.strategy])
            msg = f"{close_info.name} 平仓\n策略:{strategy_tag}\n委托价格:{price_close:.2f}\n平仓收益:{profit_rate:.2%}\n平仓依据:{close_info.close_reason}"
            await cls.send_msg(msg)

            # 记录平仓到Excel
            await CloseRecordManager.record_close_async(
                source="AUTOA",
                symbol=f"{close_info.name} {code}",
                position_side="LONG",  # A股默认做多
                entry_price=entry_price,
                close_price=price_close,
                close_amount=cls.DEFAULT_POSITION_SHARES,
                realized_pnl=realized_pnl,
                pnl_percent=profit_rate,
                close_ratio=1.0,
                strategy_tag=strategy_tag,
                close_reason=close_info.close_reason,
            )
        else:
            # 未触及止盈止损，执行移动止损逻辑
            # 参照 AUTOBN 的动态止盈止损逻辑（使用当前hl2与ATR计算上下轨）
            DECAY = cls.STOP_LOSS_DECAY
            atr_value = cls.calculate_atr(hist, period=cls.ATR_PERIOD)
            hl2 = (float(hist.iloc[-1]["high"]) + float(hist.iloc[-1]["low"])) / 2
            current_upper = hl2 + atr_value * cls.SUPERTREND_FACTOR
            current_lower = hl2 - atr_value * cls.SUPERTREND_FACTOR

            if (
                atr_value > 0
                and close_info.entry_price > 0
                and price_close < close_info.entry_price - atr_value
            ):
                close_info.strategy.append(PositionSide.DCA)
                strategy_tag = ",".join([ps.value for ps in close_info.strategy])
                msg = (
                    f"{close_info.name} 加仓\n"
                    f"策略:{strategy_tag}\n"
                    f"委托价格:{price_close:.2f}\n"
                    f"止盈:{close_info.take_profit:.2f}\n"
                    f"止损:{close_info.stop_loss:.2f}"
                )
                await cls.send_msg(msg)
                close_info.entry_price = (close_info.entry_price + price_close) / 2
                dca_count = sum(
                    1
                    for strategy in close_info.strategy
                    if strategy == PositionSide.DCA
                )
                target_take_profit = (
                    close_info.entry_price
                    + cls.DCA_TP_ATR_RATIO * atr_value * dca_count
                )
                close_info.take_profit = min(
                    close_info.take_profit,
                    target_take_profit,
                )
            else:
                # 做多: 止盈在上方，止损在下方
                # 止盈下移: 取衰减后的值和当前上轨的较小值
                initial_tp_gap = close_info.take_profit - close_info.entry_price
                tp_decay_step = initial_tp_gap * DECAY
                decayed_tp = close_info.take_profit - tp_decay_step
                close_info.take_profit = min(decayed_tp, current_upper)

                # 检测是否达到预期收益的1/3，如果是则设置止损为保护70%盈利
                profit = price_close - close_info.entry_price
                atr_trigger = max(
                    min(atr_value, close_info.entry_price * cls.ATR_TRIGGER_CAP_RATIO),
                    cls.MIN_ATR_TRIGGER,
                )
                target_profit = min(
                    initial_tp_gap / cls.TARGET_PROFIT_DIVISOR,
                    atr_trigger,
                )  # 预期收益的1/3 与 ATR触发阈值取较小值
                if profit >= target_profit:
                    # 达到目标盈利，止损设置为当前盈利回撤30%的位置
                    # 止损 = 入场价 + 盈利 * TRAILING_STOP_PROFIT_RATIO
                    trailing_stop = (
                        close_info.entry_price + profit * cls.TRAILING_STOP_PROFIT_RATIO
                    )
                    new_stop_loss = max(close_info.stop_loss, trailing_stop)
                    if new_stop_loss != close_info.stop_loss:
                        close_info.stop_loss = new_stop_loss
                        close_info.close_reason = "追踪止损(保护盈利)"
                else:
                    # 止损上移: 使用当前下轨作为参考，止损只能上移（保护利润）
                    # 取当前下轨和原止损的较大值
                    new_stop_loss = max(close_info.stop_loss, current_lower)
                    if new_stop_loss != close_info.stop_loss:
                        close_info.stop_loss = new_stop_loss
                        close_info.close_reason = "移动止损(轨道)"

            cls.alert_all["POSITIONS"][code] = close_info.model_dump()

    @classmethod
    async def on_observations(cls, code, zt_dates, open_info_dict, today):
        """
        处理观察列表中的股票，检测买入信号

        策略：低吸策略 - 在涨停次日回调后放量突破时买入
        核心逻辑：
            1. 超时清理：观察超过10天的股票自动移出
            2. 信号确认：满足以下条件时触发买入
               - 时间：观察至少24小时
               - 价格：突破10日均价、昨收、今开的最高值
               - 成交量：放量突破（今日量 > max(前2日量*1.5)）

        参数：
            code: 股票代码（如'000001'）
            zt_dates: 交易日期列表
            open_info_dict: 观察记录字典 (Pydantic Observation.model_dump())
            today: 当前日期时间
        """
        open_info = Observation.model_validate(open_info_dict)
        if today.timestamp() - open_info.timestamp > cls.OBSERVATION_TIMEOUT_SECONDS:
            cls.alert_all["OBSERVATIONS"].pop(code)
            return
        if (
            datetime.datetime.fromtimestamp(
                today.timestamp(), datetime.timezone.utc
            ).date()
            == datetime.datetime.fromtimestamp(
                open_info.timestamp, datetime.timezone.utc
            ).date()
        ):
            return
        # 获取股票历史数据（前复权，确保价格连续性）
        hist = await cls.stock_zh_a_hist(
            code,
            "date,code,open,high,low,close,preclose,volume,amount",
            start_date=zt_dates[-1],
            end_date=zt_dates[0],
            frequency="d",
            adjustflag="3",  # 前复权
        )
        if hist.empty:
            return
        # 获取开盘价、收盘价、最高价序列用于高开判断
        hist_open = hist["open"].values
        hist_close = hist["close"].values
        hist_high = hist["high"].values
        # 数据校验：无历史数据则跳过，或当前价格不高于昨日最高价则跳过
        if hist_close[-1] <= hist_open[-1]:
            return

        # 切比雪夫概率判断：检查最近成交量是否为极端异常值（显著放量）
        hist_volume = hist["volume"].values
        if len(hist_volume) >= cls.VOLUME_CHEB_REQUIRED_HISTORY:
            should_open = False
            volume_sample = hist_volume[
                cls.VOLUME_CHEB_SAMPLE_START_OFFSET : cls.VOLUME_CHEB_SAMPLE_END_OFFSET
            ]
            current_volume = hist_volume[-1]
            # 先计算 supertrend 和 ATR（两种策略都需要）
            current_atr = cls.calculate_atr(hist, period=cls.ATR_PERIOD)
            if (
                hist_open[-1] > hist_high[-2]
                and current_volume
                >= max(hist_volume[cls.VOLUME_CHEB_SAMPLE_START_OFFSET :])
                and cls.calculate_chebyshev_probability(
                    volume_sample,
                    current_volume,
                )["chebyshev_upper_bound"]
                < cls.CHEBYSHEV_EXTREME_THRESHOLD
            ):
                if PositionSide.BZ not in open_info.strategy:
                    open_info.strategy.append(PositionSide.BZ)
                should_open = True
            elif (
                PositionSide.BZ in open_info.strategy
                and cls.check_gap_up_after_break_ma10(hist)
            ):
                if PositionSide.N not in open_info.strategy:
                    open_info.strategy.append(PositionSide.N)
                should_open = True

            if should_open and current_atr > 0:
                price_close = float(hist.iloc[-1]["close"])
                # 初始化止盈止损与AUTOBN一致：基于hl2和ATR倍数计算
                hl2 = (float(hist.iloc[-1]["high"]) + float(hist.iloc[-1]["low"])) / 2
                take_profit = hl2 + current_atr * cls.SUPERTREND_FACTOR
                stop_loss = hl2 - current_atr * cls.SUPERTREND_FACTOR
                atr_percent = (
                    abs(take_profit - price_close) / price_close
                    if price_close > 0
                    else 0
                )
                # 4. 记录到持仓列表
                cls.alert_all["POSITIONS"][code] = Position(
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    close_side=OrderSide.SELL,
                    position_side=PositionSide.LONG,
                    entry_price=price_close,
                    name=open_info.name,
                    date=int(today.strftime("%Y%m%d")),
                    strategy=open_info.strategy,
                ).model_dump()

                # 5. 发送买入通知
                msg = (
                    f"==={open_info.name}**{','.join([ps.value for ps in open_info.strategy])}**===\n"
                    f"价格:{price_close:.2f}\n"
                    f"止盈:{take_profit:.2f}\n"
                    f"止损:{stop_loss:.2f}\n"
                    f"收益率:{atr_percent:.2%}\n"
                )
                await cls.send_msg(msg)

                # 6. 从观察列表移除
                cls.alert_all["OBSERVATIONS"][code] = open_info.model_dump()
        else:
            return

    @classmethod
    async def filter_stocks(cls):
        """
        筛选符合量能条件的A股股票

        功能：从涨停股池中筛选出符合低吸条件的股票
        策略：寻找有上涨动能但可能进入回调的优质股票
        返回：
            符合条件的股票代码和名称集合
        """
        # 获取交易日历信息
        today = datetime.datetime.today()
        # 9:30前不执行：小时小于9，或9点但分钟小于30
        is_before_open = today.hour < cls.MARKET_OPEN_HOUR or (
            today.hour == cls.MARKET_OPEN_HOUR and today.minute < cls.MARKET_OPEN_MINUTE
        )
        # 收盘后不执行：小时大于15，或者小时等于15且分钟大于5
        is_after_close = today.hour > cls.MARKET_CLOSE_HOUR or (
            today.hour == cls.MARKET_CLOSE_HOUR
            and today.minute > cls.MARKET_CLOSE_MINUTE
        )
        if (
            (cls.zt_dates and today.strftime("%Y-%m-%d") not in cls.zt_dates)
            or is_before_open
            or is_after_close
        ):
            return []
        if not cls.zt_dates:
            cls.zt_dates = await cls.get_last_trading_days(today)
            if not cls.zt_dates:
                return []
        selected = set()  # 存储符合条件的股票
        if today.hour == cls.MARKET_CLOSE_HOUR:
            async def _write_alert_all_async():
                async with aiofiles.open(cls.alert_all_file, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(cls.alert_all, ensure_ascii=False, indent=4))

            await asyncio.wait_for(
                _write_alert_all_async(), timeout=cls.FILE_IO_TIMEOUT_SECONDS
            )
            zt_df = await asyncio.wait_for(
                asyncio.to_thread(
                    ak.stock_zt_pool_em, date=cls.zt_dates[0].replace("-", "")
                ),
                timeout=cls.AKSHARE_TIMEOUT_SECONDS,
            )
            stock_codes = zt_df[["代码", "名称", "连板数"]].values.tolist()
            for code in stock_codes:
                hist = await cls.stock_zh_a_hist(
                    code[0],  # 股票代码
                    "date,code,open,high,low,close,preclose,volume,amount",
                    start_date=cls.zt_dates[-1],
                    end_date=cls.zt_dates[0],
                    frequency="d",  # 日K
                    adjustflag="3",  # 3：前复权；1：不复权；2：后复权
                )
                if hist.empty:
                    continue
                price_close = hist.iloc[-1]["close"]

                # 已在观察列表且当日再次涨停：刷新观察时间（即使在持仓也允许更新）
                if code[0] in cls.alert_all["OBSERVATIONS"]:
                    open_info = Observation.model_validate(
                        cls.alert_all["OBSERVATIONS"][code[0]]
                    )
                    open_info.price = float(price_close)
                    open_info.timestamp = today.timestamp()
                    cls.alert_all["OBSERVATIONS"][code[0]] = open_info.model_dump()
                    continue

                selected.add(f"{code[1]}")
                cls.alert_all["OBSERVATIONS"][code[0]] = Observation(
                    price=float(price_close),
                    timestamp=today.timestamp(),
                    side=OrderSide.BUY,
                    strategy=[],
                    name=code[1],  # 股票名称
                ).model_dump()

            cls.zt_dates.clear()
            cls.hist_cache.clear()
            return selected

        semaphore = asyncio.Semaphore(cls.MAX_CONCURRENT_REQUESTS)
        window_seconds = cls.BATCH_WINDOW_MINUTES * 60
        window_id = int(today.timestamp() // window_seconds)
        slot = today.minute % cls.BATCH_SLOT_COUNT

        if cls._batch_window_id != window_id:
            cls._batch_window_id = window_id
            cls._batch_observations_snapshot = sorted(
                [
                    code
                    for code in cls.alert_all["OBSERVATIONS"].keys()
                    if code not in cls.alert_all["POSITIONS"]
                ]
            )

        observation_snapshot = cls._batch_observations_snapshot
        batch_observation_codes = [
            code
            for index, code in enumerate(observation_snapshot)
            if index % cls.BATCH_SLOT_COUNT == slot
        ]
        position_symbols = list(cls.alert_all["POSITIONS"].keys())
        effective_symbols = list(dict.fromkeys(batch_observation_codes + position_symbols))

        cls.logger.info(
            f"A任务开始 - window:{window_id} slot:{slot}/{cls.BATCH_SLOT_COUNT} "
            f"快照数量:{len(observation_snapshot)} 批次数量:{len(batch_observation_codes)} "
            f"持仓数量:{len(position_symbols)} 实际处理数量:{len(effective_symbols)}"
        )

        success = set()

        async def _run_symbol(code):
            async with semaphore:
                if code in cls.alert_all["POSITIONS"]:
                    close_info = cls.alert_all["POSITIONS"].get(code)
                    if close_info is None:
                        return
                    await cls.on_positions(code, cls.zt_dates, close_info, today)
                else:
                    open_info = cls.alert_all["OBSERVATIONS"].get(code)
                    if open_info is None:
                        return
                    await cls.on_observations(code, cls.zt_dates, open_info, today)
                success.add(code)

        tasks = [_run_symbol(code) for code in effective_symbols]
        if tasks:
            await asyncio.gather(*tasks)
        gc.collect()  # 垃圾回收，释放内存
        cls.logger.info(
            f"A任务结束 - window:{window_id} slot:{slot}/{cls.BATCH_SLOT_COUNT} "
            f"批次成功数量:{len(success)}"
        )
        return selected

    @classmethod
    async def monitor_stocks(cls):
        """
        监控A股并发送通知

        功能：筛选符合条件的A股股票，并通过企业微信发送通知
        策略：低吸策略，寻找回调买入机会
        """
        start_ts = time.time()
        try:
            # 设置超时时间为10分钟，防止任务卡住
            cls.logger.info("A股监控任务开始")
            await asyncio.wait_for(
                cls._monitor_stocks_impl(), timeout=cls.MONITOR_TIMEOUT
            )
            cls.logger.info(f"A股监控任务结束，总耗时:{time.time() - start_ts:.2f}s")
        except asyncio.TimeoutError:
            error_msg = f"A股监控任务超时({cls.MONITOR_TIMEOUT}秒)，已强制中断"
            cls.logger.error(error_msg)
            await cls.send_msg(error_msg)
        except Exception as e:
            error_msg = f"A股监控任务异常: {str(e)}"
            cls.logger.error(error_msg)
            cls.logger.exception("A股监控任务发生异常")
            await cls.send_msg(error_msg)

    @classmethod
    async def _monitor_stocks_impl(cls):
        """A股监控的实际实现"""
        # 登录系统（使用异步执行，避免阻塞事件循环）
        await asyncio.wait_for(
            asyncio.to_thread(bs.login), timeout=cls.BAOSTOCK_TIMEOUT_SECONDS
        )
        try:
            # 筛选符合量能条件的股票
            filtered = await cls.filter_stocks()
            cls.logger.info(f"符合量能条件的股票：{filtered}")

            # 如果有符合条件的股票，发送通知
            if filtered:
                # 构建消息内容
                content = f"===A{len(filtered)} 首板===\n" + "\n-------\n".join(
                    filtered
                )
                # 发送到企业微信群
                await cls.send_msg(content)

        finally:
            # 确保总是登出，即使发生异常（使用异步执行）
            await asyncio.wait_for(
                asyncio.to_thread(bs.logout),
                timeout=cls.BAOSTOCK_TIMEOUT_SECONDS,
            )


# 注册AUTOA的退出处理函数,在脚本退出时保存A股数据
atexit.register(AUTOA._save_alert_all_on_exit)


def handle_exit_signal(signum, frame):
    """处理系统退出信号，确保触发atexit"""
    signal_name = "SIGINT (Ctrl+C)" if signum == signal.SIGINT else "SIGTERM"
    logger = logging.getLogger("AUTOA")
    logger.info(f"接收到退出信号 {signal_name}, 准备退出...")
    # 调用 sys.exit(0) 会触发 atexit 注册的函数
    sys.exit(0)


# 注册信号处理，确保程序优雅退出
signal.signal(signal.SIGINT, handle_exit_signal)
signal.signal(signal.SIGTERM, handle_exit_signal)

# 配置根日志记录器
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


async def main():
    """
    主函数：设置定时任务并启动调度器

    功能：配置并启动所有定时任务
    任务1：A股监控（交易时段执行）
    任务2：币安市场分析（每分钟执行）
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 从环境变量或配置文件加载密钥
    qy_key = os.getenv("QY_WECHAT_KEY", "095984b1-5bc0-43ac-8037-d65a9608d120")
    if not qy_key:
        logger = logging.getLogger("AUTOA")
        logger.warning("未设置环境变量 QY_WECHAT_KEY，消息通知功能将不可用")
        # 可以选择：1) 抛出异常退出  2) 使用空密钥继续运行
        # 这里选择继续运行但禁用通知
        qy_key = ""
    autobn_qy_key = AUTOA.qy_key

    autobn = AUTOBN.from_cfg(
        bn_api_file=os.path.join(current_dir, "bn.json"),
        alert_all_file=os.path.join(current_dir, "alert_all.json"),
        qy_key=autobn_qy_key,
        signal_qy_key=qy_key,
    )

    # 初始化任务调度器，配置全局日志级别
    scheduler = AsyncIOScheduler()
    logging.getLogger("apscheduler").setLevel(
        logging.WARNING
    )  # 减少调度器自身的日志输出

    logger = logging.getLogger("AUTOA")
    logger.info("配置A股监控任务...")
    # 设置A股监控定时任务
    scheduler.add_job(
        AUTOA.monitor_stocks,  # 执行的函数
        "cron",  # 调度类型：按日历规则
        hour="09-15",  # 交易时段：09:00 - 15:00
        minute="*",  # 每分钟执行一次
        second="00",  # 整点秒数
        day_of_week="mon-fri",  # 周一至周五（交易日）
        timezone="Asia/Shanghai",  # 上海时区
        misfire_grace_time=60,  # 错过执行的宽限时间（秒）
        max_instances=1,  # 同一时间只允许1个实例运行
        coalesce=False,  # 改为False，避免合并错过的执行导致任务堆积和卡住
        name="股票监控任务",  # 任务名称
    )

    logger.info("配置A股每日持仓推送任务...")
    scheduler.add_job(
        AUTOA.push_daily_positions,
        "cron",
        hour=9,
        minute=0,
        second=0,
        timezone="Asia/Shanghai",
        misfire_grace_time=300,
        max_instances=1,
        coalesce=True,
        name="A股每日持仓推送任务",
    )

    logger = logging.getLogger("AUTOBN")
    logger.info("配置币安市场分析任务...")
    # 设置币安市场分析定时任务
    scheduler.add_job(
        autobn.rzq_market,  # 执行的函数
        "cron",  # 调度类型：按日历规则
        hour="*",  # 每小时执行
        minute="*",  # 每分钟
        second="00",  # 整点秒数
        timezone="Asia/Shanghai",  # 上海时区
        args=("BN",),  # 传递参数
        misfire_grace_time=10,  # 错过执行的宽限时间（秒）
        max_instances=1,  # 同一时间只允许1个实例运行
        coalesce=False,  # 改为False，避免合并错过的执行导致任务堆积和卡住
        name="币安市场分析任务",  # 任务名称
    )

    logger = logging.getLogger("AUTOA")
    logger.info("启动调度器...")
    # 启动调度器
    scheduler.start()
    logger.info("调度器已启动，等待任务触发...")

    # 创建一个永不触发的事件，使程序一直运行
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发（实际不会发生）


if __name__ == "__main__":
    """
    程序入口：初始化配置并启动主程序

    功能：初始化所有必要的配置和客户端，然后启动主程序
    """
    logger = logging.getLogger("AUTOA")
    logger.info("autoBN启动")
    # 启动主程序（调度器在main函数中初始化）
    asyncio.run(main())
