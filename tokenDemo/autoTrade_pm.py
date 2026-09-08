# ==================== 标准库导入 ====================
import asyncio
import atexit
import datetime
import json
import logging
import math
import os
import signal
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from enum import Enum
from typing import List, Literal, Optional

# ==================== 第三方库导入 ====================
import aiohttp
import akshare as ak
import pandas as pd
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
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter

try:
    from tokenDemo.pushplus_notifications import (
        DailyPosition,
        TradeNotification,
        format_daily_positions_notification,
        format_trade_notification,
        send_pushplus,
    )
except ModuleNotFoundError:
    from pushplus_notifications import (
        DailyPosition,
        TradeNotification,
        format_daily_positions_notification,
        format_trade_notification,
        send_pushplus,
    )

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


@dataclass(frozen=True)
class CloseExecution:
    order: dict
    entry_price: float
    amount: float
    ratio: float


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
    stop_guard_threshold: float = 0.0  # 止损触发辅助阈值（AUTOBN/AUTOA按各自策略写入）
    close_reason: str = (
        ""  # 平仓依据（止盈/初始止损/追踪止损/移动止损等）
    )
    long_short_ratio: str = ""  # 开仓信号当时的多空比
    basis_rate: str = ""  # 开仓信号当时的基差率


class Observation(BaseModel):
    """
    观察列表信息数据类 (AUTOBN/AUTOA 通用)

    用途：记录待观察的交易机会
    字段：
        price: 触发价格（AUTOA中未出现BZ前为入池价格，出现BZ后为观察期最低价）
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
    bz_reference_high: Optional[float] = None
    earliest_open_timestamp: Optional[float] = None
    reopen_pending_date: Optional[str] = None  # 已平仓但尚未确认实际重开交易日

    def is_reopen_cooldown_active(self, current_timestamp: float) -> bool:
        return self.reopen_pending_date is not None or (
            self.earliest_open_timestamp is not None
            and current_timestamp < self.earliest_open_timestamp
        )


def format_strategy_tags(strategies: List[PositionSide | str]) -> str:
    counts = {}
    ordered_values = []
    for strategy in strategies or []:
        value = strategy.value if isinstance(strategy, Enum) else str(strategy)
        if value not in counts:
            counts[value] = 0
            ordered_values.append(value)
        counts[value] += 1
    return ",".join(
        f"{value}*{counts[value]}" if counts[value] > 1 else value
        for value in ordered_values
    )


def _chebyshev_result(mean, std, value):
    """两种市场共用的概率结果计算；保留现有零方差约定。"""
    deviation = value - mean
    if std == 0:
        k = float("inf") if deviation != 0 else 0.0
        upper_bound = 0.0
    else:
        k = abs(deviation) / std
        upper_bound = 1.0 if k <= 1 else 1 / k**2
    return {
        "mean": mean,
        "std": std,
        "k": k,
        "chebyshev_upper_bound": upper_bound,
        "min_probability_in_range": 1 - upper_bound,
        "deviation": deviation,
    }


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
    _pending_records = []
    _batch_lock = None
    _batch_lock_loop = None

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
        "多空比",
        "基差率",
    ]

    @classmethod
    def _record_close_batch(cls, records):
        with cls._lock:
            existing_sheets = {}
            if os.path.exists(cls._excel_file):
                try:
                    with pd.ExcelFile(cls._excel_file, engine="openpyxl") as xls:
                        for name in xls.sheet_names:
                            existing_sheets[name] = pd.read_excel(xls, sheet_name=name)
                except Exception:
                    pass

            records_by_sheet = {}
            for record in records:
                sheet_name = cls.SHEET_NAMES.get(record["source"], record["source"])
                records_by_sheet.setdefault(sheet_name, []).append(
                    {key: value for key, value in record.items() if key != "source"}
                )

            for sheet_name, sheet_records in records_by_sheet.items():
                df = existing_sheets.get(sheet_name, pd.DataFrame(columns=cls.COLUMNS))
                existing_sheets[sheet_name] = pd.concat(
                    [df, pd.DataFrame(sheet_records)], ignore_index=True
                )

            with pd.ExcelWriter(cls._excel_file, engine="openpyxl") as writer:
                for name, data in existing_sheets.items():
                    data.to_excel(writer, sheet_name=name, index=False)

    @classmethod
    def enqueue_close(
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
        long_short_ratio: str = "",
        basis_rate: str = "",
    ):
        record = {
            "source": source,
            "平仓时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            "多空比": long_short_ratio,
            "基差率": basis_rate,
        }
        cls._pending_records.append(record)
        return record

    @classmethod
    async def record_close_async(cls, *args, **kwargs):
        """兼容现有异步调用；先同步入队，再批量写入。"""
        cls.enqueue_close(*args, **kwargs)
        await asyncio.sleep(0)
        await cls.flush_pending_records()

    @classmethod
    async def flush_pending_records(cls):
        if not cls._pending_records:
            return
        current_loop = asyncio.get_running_loop()
        if cls._batch_lock is None or cls._batch_lock_loop is not current_loop:
            cls._batch_lock = asyncio.Lock()
            cls._batch_lock_loop = current_loop
        async with cls._batch_lock:
            records = cls._pending_records[:]
            if not records:
                return
            # 线程写入无法被 asyncio 取消；保持锁直到写入结果确定，避免重试重复记账。
            write_task = asyncio.create_task(asyncio.to_thread(cls._record_close_batch, records))
            try:
                await asyncio.shield(write_task)
            except asyncio.CancelledError:
                try:
                    await write_task
                except Exception:
                    cls._logger.exception("平仓记录写入失败，保留待重试")
                else:
                    del cls._pending_records[: len(records)]
                raise
            except Exception:
                cls._logger.exception("平仓记录写入失败，保留待重试")
                return
            del cls._pending_records[: len(records)]
            cls._logger.info(f"平仓记录保存完成，共{len(records)}条")


class AUTOBN:
    """币安期货自动交易类"""

    # ==================== 并发控制常量 ====================
    MAX_CONCURRENT_REQUESTS = 8  # 最大并发请求数

    # ==================== 时间常量 ====================
    BZ_OBSERVATION_TIMEOUT_SECONDS = 24 * 60 * 60  # BZ观察记录超时时间（24小时）
    BD_OBSERVATION_TIMEOUT_SECONDS = 7 * 24 * 60 * 60  # BD观察记录超时时间（7天）
    RETRY_DELAY_SECONDS = 2  # 重试延迟（秒）
    CLOSE_RETRY_DELAY = 3  # 平仓重试延迟（秒）

    # ==================== K线相关常量 ====================
    KLINE_LIMIT = 30  # K线数据条数（与AUTOA实际消费量对齐）

    # ==================== 多空比相关常量 ====================
    LONG_SHORT_RATIO_LIMIT = 30  # 多空比数据查询数量限制
    EXCHANGE_INFO_CACHE_TTL = 6 * 60 * 60  # 交易所元数据缓存过期时间（6小时）
    FIVE_MIN_PERIOD_MS = 300_000  # 5m周期长度（毫秒），用于算当前周期边界
    OI_DELTA_LONG_RATIO_WEIGHT = 0.4  # LONG融合公式中(oi_5m-oi_1d)项权重

    # ==================== ATR风控常量 ====================
    ATR_PERIOD = 7  # ATR计算周期：加密市场一周
    TAKE_PROFIT_ATR_FACTOR = 3.0  # AUTOBN止盈价与止盈轨ATR倍数
    STOP_LOSS_ATR_FACTOR = 1.0  # AUTOBN止损价与止损轨ATR倍数
    ATR_TRIGGER_CAP_RATIO = 0.05
    ATR_HL2_CAP_RATIO = 0.1  # ATR返回值上限比例（不超过hl2的10%）
    MIN_ATR_TRIGGER = 1e-8
    DCA_TP_ATR_RATIO = 0.5  # DCA触发后止盈收紧系数(按ATR与触发次数)
    STOP_LOSS_DECAY_PER_MINUTE = 0.0001  # 每分钟止盈止损衰减比例 (0.01%)

    # ==================== 回溯周期常量 ====================
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
    SHORT_OI_CHEB_THRESHOLD = 0.05  # SHORT入池的1d OI堆积极端阈值（5%）

    # ==================== BD做空入池/扣扳机常量 ====================
    BD_VOLUME_LOOKBACK_COUNT = 10  # 入池成交量回看总根数
    BD_VOLUME_RECENT_COUNT = 3  # 入池成交量近期区间根数
    BD_OI_LOOKBACK_COUNT = 10  # 入池1d OI回看总根数
    BD_OI_RECENT_COUNT = 3  # 入池1d OI近期区间根数
    BZ_LONG_OI_DRAWDOWN_RATIO = 0.1  # BZ多头：自开仓5m OI回撤10%触发平仓
    BD_OI_DRAWDOWN_RATIO = 0.1  # 扣扳机：5m OI 需自30日峰值回撤的比例（10%）

    # ==================== 基差率常量 ====================
    BASIS_RATE_THRESHOLD = 0.02  # 基差率开仓阈值（2%）
    BASIS_RATE_CACHE_TTL = 300  # 基差率缓存过期时间（秒，5分钟）

    # ==================== 平仓相关常量 ====================
    PARTIAL_CLOSE_RATIO = 0.7  # 部分平仓比例 (止盈时使用)
    TRAILING_STOP_PROFIT_RATIO = 0.7  # 空头追踪止损盈利保护比例 (保护70%盈利，允许30%回撤)
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
    LONG_OI_CHEB_EXCLUDE_RECENT_COUNT = 6
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
        # 支持键：leverage, health4open,
        #        session/session_verify/session_headers,
        #        alert_all_file/allert_all_file, api_key, api_secret
        # AUTOBN 不使用企业微信，消息渠道由 send_msg 的事件参数决定。
        # 交易参数配置（可覆盖）
        obj.leverage = kwargs.get("leverage", cls.DEFAULT_LEVERAGE)
        obj.health4open = kwargs.get("health4open", cls.DEFAULT_HEALTH_THRESHOLD)

        obj.alert_all_file = kwargs.get(
            "alert_all_file", kwargs.get("allert_all_file", "alert_all.json")
        )

        # 优先级：kwargs参数 > 环境变量
        api_key = kwargs.get("api_key") or os.getenv("BINANCE_API_KEY")
        api_secret = kwargs.get("api_secret") or os.getenv("BINANCE_API_SECRET")

        # 安全检查：确保密钥已配置
        if not api_key or not api_secret:
            raise ValueError(
                "币安API密钥未配置！请设置环境变量 BINANCE_API_KEY 和 "
                "BINANCE_API_SECRET，或在调用 from_cfg() 时传入 api_key 和 "
                "api_secret 参数"
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

        obj.symbols_info = {}
        obj._exchange_info_cache = None
        obj._exchange_info_cache_timestamp = 0.0
        obj._http_session = None
        obj.is_early_morning = False
        # 四个行情缓存统一口径，末根时间戳就是缓存的新旧标记。
        # 末根已是"当前时刻能拿到的最新"就不拉；否则拉回来比末根时间戳，新的那份才替换。
        # 取用时一律读缓存，不因为末根滞后就把数据判掉。
        obj._lsr_1h_cache = {}
        obj._oi_history_cache = {}
        obj._oi_5m_cache = {}
        obj._lsr_5m_cache = {}
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

    async def _get_http_session(self):
        if self._http_session is None or self._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=self.MESSAGE_TIMEOUT_SECONDS)
            self._http_session = aiohttp.ClientSession(timeout=timeout)
        return self._http_session

    async def close_http_session(self):
        if self._http_session is not None and not self._http_session.closed:
            await self._http_session.close()
        self._http_session = None

    async def send_msg(
        self,
        msg: str | TradeNotification,
        *,
        channel: Literal["feishu", "pushplus"] | None = None,
    ) -> None:
        """按指定渠道发送 AUTOBN 通知。"""
        try:
            log_message = msg.content if isinstance(msg, TradeNotification) else msg
            self.logger.info(f"发送消息: {log_message}")
            if channel == "pushplus":
                if not isinstance(msg, TradeNotification):
                    self.logger.warning("PushPlus 渠道需要 TradeNotification，跳过消息发送")
                    return
                try:
                    await send_pushplus(msg)
                except Exception as e:
                    self.logger.error(f"PushPlus 消息发送异常: {str(e)}")
                return

            if channel == "feishu":
                if not isinstance(msg, str):
                    self.logger.warning("飞书渠道需要文本消息，跳过消息发送")
                    return
                webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "")
                if not webhook_url:
                    self.logger.warning("未配置飞书机器人 webhook，跳过飞书消息")
                    return
                http_session = await self._get_http_session()
                try:
                    async with http_session.post(
                        url=webhook_url,
                        json={
                            "msg_type": "text",
                            "content": {"text": msg},
                        },
                    ) as response:
                        if response.status != 200:
                            response_text = await response.text()
                            self.logger.error(
                                f"飞书消息发送失败，状态码: {response.status}，响应: {response_text}"
                            )
                except Exception as e:
                    self.logger.error(f"飞书消息发送异常: {str(e)}")
                return

            if channel is not None:
                self.logger.warning(f"未识别的消息渠道: {channel}")
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

    async def get_amount_close(self, symbol):
        """
        获取指定交易对的持仓数量 (异步)

        功能：查询币安账户中指定交易对的当前持仓数量
        用途：用于平仓时确定需要平仓的数量
        参数：
            symbol: 交易对符号，如'BTCUSDT'
        返回：
            成功返回[持仓数量绝对值, 开仓均价]，确认无持仓返回[0, 0]，查询失败返回None
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
            return None

    async def open_bn_position(
        self,
        symbol,
        side,
        positionSide,
        take_profit_price=None,
        stop_loss_price=None,
        open_info=None,
        open_signal=None,
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
            if symbol not in self.symbols_info:
                await self.send_msg(f"{symbol} 开仓失败：找不到交易对信息")
                return None
            if stop_loss_price is None or stop_loss_price <= 0:
                await self.send_msg(f"{symbol} 开仓失败：未提供有效止损价格")
                return None
            if take_profit_price is None or take_profit_price <= 0:
                await self.send_msg(f"{symbol} 开仓失败：未提供有效止盈价格")
                return None

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

            if open_signal is not None:
                try:
                    await self.send_msg(open_signal, channel="feishu")
                except Exception as e:
                    self.logger.error(f"{symbol} 开仓信号发送异常，不阻断下单: {str(e)}")

            tx = await self._call_api(
                self.papi_client.rest_api.new_um_order,
                symbol=symbol,
                side=self._to_papi_side(side),
                type=self._to_papi_order_type("MARKET"),
                quantity=amount,
                position_side=self._to_papi_position_side(positionSide),
                recv_window=60000,
            )
            rate_show = take_profit_gap / markPrice
            strategy_tag = format_strategy_tags(open_info.strategy)
            msg = f"{symbol} 开仓\n策略:{strategy_tag}\n持仓方向:{positionSide}\n杠杆:{actual_leverage}x\n委托数量:{tx.get('origQty', 0)}\n委托价格:{markPrice}\n名义价值:{notional} USDT\n账户余额:{total_balance:.2f}\n仓位比例:{notional / total_balance:.2%}\n收益率:{rate_show:.2%}"
            await self.send_msg(
                format_trade_notification("AUTOBN", "开仓", symbol, msg),
                channel="pushplus",
            )
            return account_data
        except Exception as e:
            error_msg = f"{symbol} 开仓失败：{str(e)}"
            self.logger.exception(error_msg)
            return None

    def _handle_closed_position_observation(self, symbol, close_info, close_timestamp):
        if PositionSide.BD in close_info.strategy:
            self.alert_all["OBSERVATIONS"].pop(symbol, None)
            return

        open_info_dict = self.alert_all["OBSERVATIONS"].get(symbol)
        if not open_info_dict:
            return

        open_info = Observation.model_validate(open_info_dict)
        open_info.earliest_open_timestamp = (
            close_timestamp + self.REOPEN_COOLDOWN_SECONDS
        )
        self.alert_all["OBSERVATIONS"][symbol] = open_info.model_dump()

    def _clear_closed_position(self, symbol, close_info):
        self._handle_closed_position_observation(symbol, close_info, time.time())
        if symbol in self.alert_all["POSITIONS"]:
            self.alert_all["POSITIONS"].pop(symbol)

    async def _execute_close_order(self, symbol, close_info, price_close, close_ratio):
        """执行平仓并返回确认成功的结果；保留现有请求异常重试策略。"""
        amount_price = await self.get_amount_close(symbol)
        if amount_price is None:
            await self.send_msg(f"{symbol} 平仓跳过：查询持仓数量失败")
            return
        amount = amount_price[0]
        if not amount:
            await self.send_msg(f"{symbol} 平仓跳过：确认持仓数量为0")
            self._clear_closed_position(symbol, close_info)
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
            await self.send_msg(f"{symbol} 平仓跳过：平仓数量精度处理后为0")
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
            except Exception:
                await asyncio.sleep(self.CLOSE_RETRY_DELAY)
                self.logger.exception(f"平仓 {symbol} 失败，当前价格: {price_close}")
                msg = f"bn平仓{symbol}失败，当前价格:{price_close}"
                await self.send_msg(msg)
                current_amount_price = await self.get_amount_close(symbol)
                if current_amount_price is None:
                    await self.send_msg(
                        f"{symbol} 平仓跳过：重试后查询持仓数量失败"
                    )
                    return None
                current_amount = current_amount_price[0]
                if not current_amount:
                    await self.send_msg(
                        f"{symbol} 平仓跳过：重试后确认持仓数量为0"
                    )
                    self._clear_closed_position(symbol, close_info)
                    return None
                close_amount = current_amount * close_ratio
                close_amount = float(
                    Decimal(str(close_amount)).quantize(
                        self.symbols_info.get(symbol)["quantityPrecision"],
                        rounding=ROUND_DOWN,
                    )
                )
                continue

            return CloseExecution(
                order=tx,
                entry_price=amount_price[1] if amount_price[1] > 0 else close_info.entry_price,
                amount=close_amount,
                ratio=close_ratio,
            )
        return None

    def _apply_close_state(self, symbol, close_info, atr_value, price_close, take_profit_stage):
        """仅处理确认成交后的策略状态，先写回，再进行后续查询和通知。"""
        is_long = close_info.position_side == PositionSide.LONG
        if take_profit_stage is not None:
            close_info.tp_count += 1
        take_profit = close_info.take_profit
        stop_loss = close_info.stop_loss
        if atr_value > 0:
            atr_take_profit, atr_stop_loss = self.calc_stop_profit_loss(
                price_close, is_long=is_long, atr=atr_value
            )
            if atr_take_profit > 0 and atr_stop_loss > 0:
                take_profit, stop_loss = atr_take_profit, atr_stop_loss

        if take_profit_stage == "first":
            next_tp_distance = min(atr_value, price_close * self.ATR_TRIGGER_CAP_RATIO)
            if is_long:
                take_profit = price_close + next_tp_distance
            else:
                profit = close_info.entry_price - price_close
                stop_loss = min(
                    stop_loss,
                    close_info.entry_price - profit * self.TRAILING_STOP_PROFIT_RATIO,
                )
                take_profit = price_close - next_tp_distance

        close_info.take_profit = take_profit
        # 多头只保留仓位计算参考价，价格止损仅对空头生效。
        close_info.stop_loss = stop_loss
        if symbol in self.alert_all["POSITIONS"]:
            self.alert_all["POSITIONS"][symbol] = close_info.model_dump()

    async def close_bn_position(
        self, symbol, close_info, atr_value, price_close, close_ratio=1.0,
        *, take_profit_stage: Literal["first", "regular"] | None = None,
    ):
        """确认成交后统一更新策略状态、记录并通知；成功返回symbol，失败返回None。"""
        execution = await self._execute_close_order(symbol, close_info, price_close, close_ratio)
        if execution is None:
            return None

        partial_close = execution.ratio < 1
        if partial_close:
            self._apply_close_state(symbol, close_info, atr_value, price_close, take_profit_stage)
        is_long = close_info.position_side == PositionSide.LONG
        price_diff = (
            price_close - execution.entry_price
            if is_long else execution.entry_price - price_close
        )
        realized_pnl = price_diff * execution.amount
        pnl_percent = price_diff / execution.entry_price if execution.entry_price else 0
        strategy_tag = format_strategy_tags(close_info.strategy)
        CloseRecordManager.enqueue_close(
            source="AUTOBN",
            symbol=symbol,
            position_side=close_info.position_side.value,
            entry_price=execution.entry_price,
            close_price=price_close,
            close_amount=execution.amount,
            realized_pnl=realized_pnl,
            pnl_percent=pnl_percent,
            close_ratio=execution.ratio,
            strategy_tag=strategy_tag,
            close_reason=close_info.close_reason,
            long_short_ratio=close_info.long_short_ratio,
            basis_rate=close_info.basis_rate,
        )

        remaining_amount_price = await self.get_amount_close(symbol)
        if remaining_amount_price is None:
            self.logger.warning(f"{symbol} 平仓后查询剩余持仓失败，保留本地状态待核对")
        elif remaining_amount_price[0] == 0:
            self._clear_closed_position(symbol, close_info)
        elif not partial_close:
            # 全平可能因数量精度留有余仓；只有确认仍有持仓才调整下一阶段。
            self._apply_close_state(symbol, close_info, atr_value, price_close, take_profit_stage)

        msg = (
            f"{symbol} 平仓\n策略:{strategy_tag}\n持仓方向:{close_info.position_side.value}"
            f"\n委托价格:{price_close}\n委托数量:{execution.order.get('origQty', 0)}"
            f"\n平仓比例:{execution.ratio:.2%}\n平仓盈亏:{realized_pnl} USDT"
            f"\n平仓收益:{pnl_percent:.2%}\n止盈次数:{close_info.tp_count}"
            f"\n平仓依据:{close_info.close_reason}"
        )
        await self.send_msg(
            format_trade_notification("AUTOBN", "平仓", symbol, msg), channel="pushplus"
        )
        return symbol

    @staticmethod
    def _bar_timestamp_ms(item):
        """统一成毫秒时间戳；缺失返回None"""
        raw = item.get("timestamp")
        if raw is None:
            return None
        timestamp_ms = int(float(raw))
        if timestamp_ms < 10**12:  # 容错：秒级时间戳换算成毫秒
            timestamp_ms *= 1000
        return timestamp_ms

    @classmethod
    def _is_current_5m_bar(cls, item) -> bool:
        """缓存那根是否已是当前5m边界那根：对上就不用再拉（时间戳是收盘时刻）"""
        timestamp_ms = cls._bar_timestamp_ms(item)
        if timestamp_ms is None:
            return False
        period_ms = cls.FIVE_MIN_PERIOD_MS
        return timestamp_ms == int(time.time() * 1000) // period_ms * period_ms

    @classmethod
    def _is_newer_bar(cls, fetched, cached) -> bool:
        """拉回来的比缓存里那根新才值得换；没缓存时任何带时间戳的都算新"""
        fetched_ms = cls._bar_timestamp_ms(fetched)
        if fetched_ms is None:
            return False
        if not cached:
            return True
        cached_ms = cls._bar_timestamp_ms(cached[-1])
        return cached_ms is None or fetched_ms > cached_ms

    async def _get_oi_5m_data(self, symbol):
        return await self._get_5m_data(
            symbol, self._oi_5m_cache,
            self.market_client.rest_api.open_interest_statistics, "持仓量",
        )

    async def _get_5m_data(self, symbol, cache, api_method, data_name):
        """缓存已是当期那根就不拉；否则拉回来比时间戳，更新才换缓存，最后都用缓存。"""
        cached = cache.get(symbol)
        if cached and self._is_current_5m_bar(cached[-1]):
            return cached

        try:
            data = await self._call_api(
                api_method,
                symbol=symbol,
                period="5m",
                limit=1,
            )
        except Exception as e:
            self.logger.error(
                f"{symbol}获取5m{data_name}数据失败: {type(e).__name__}: {e!r}"
            )
            return cache.get(symbol)

        if data and self._is_newer_bar(data[-1], cached):
            cache[symbol] = data
        return cache.get(symbol)

    @staticmethod
    def _utc_history_boundary_ms(dtn: datetime, period: str) -> int:
        """返回历史序列当前可用的UTC周期边界，仅支持1d和1h。"""
        utc_boundary = datetime.datetime.fromtimestamp(
            dtn.timestamp(), datetime.timezone.utc
        ).replace(minute=0, second=0, microsecond=0)
        if period == "1d":
            utc_boundary = utc_boundary.replace(hour=0)
        elif period != "1h":
            raise ValueError(f"不支持的历史数据周期: {period}")
        return int(utc_boundary.timestamp() * 1000)

    async def _get_oi_history_data(
        self, symbol: str, dtn: datetime, period: str
    ):
        """按1d/1h周期隔离缓存历史OI，新的完整序列才替换对应缓存。"""
        available_before_ts = self._utc_history_boundary_ms(dtn, period)
        cache_key = (symbol, period)
        cached = self._oi_history_cache.get(cache_key)
        if cached and self._bar_timestamp_ms(cached[-1]) == available_before_ts:
            return cached

        try:
            oi_history = await self._call_api(
                self.market_client.rest_api.open_interest_statistics,
                symbol=symbol,
                period=period,
                limit=self.OI_QUERY_LIMIT,
            )
        except Exception as e:
            self.logger.error(
                f"{symbol}获取{period}持仓量数据失败: {type(e).__name__}: {e!r}"
            )
            return self._oi_history_cache.get(cache_key)

        available_oi = [
            item
            for item in (oi_history or [])
            if item.get("timestamp") is not None
            and int(item["timestamp"]) <= available_before_ts
        ]
        if len(available_oi) >= self.OI_QUERY_LIMIT and self._is_newer_bar(
            available_oi[-1], cached
        ):
            self._oi_history_cache[cache_key] = available_oi
        return self._oi_history_cache.get(cache_key)

    async def _get_bd_oi_windows(self, symbol, dtn: datetime):
        """返回BD入池实时窗口和开仓使用的已完成日线OI窗口。"""
        oi_1d = await self._get_oi_history_data(symbol, dtn, "1d")
        if not oi_1d or len(oi_1d) < self.OI_QUERY_LIMIT:
            return None, None

        oi_5m = await self._get_oi_5m_data(symbol)
        if not oi_5m:
            return None, None
        latest_oi_5m = oi_5m[-1]

        completed_oi = [float(item["sumOpenInterest"]) for item in oi_1d]
        realtime_oi = completed_oi + [
            float(latest_oi_5m["sumOpenInterest"])
        ]
        return realtime_oi, completed_oi

    async def check_side(
        self,
        semaphore,
        symbol,
        positionSide,
        dtn: datetime = None,
    ):
        """
        检查增仓信号，判断是否适合开仓
        """
        async with semaphore:
            try:
                if positionSide == PositionSide.SHORT.value:
                    realtime_oi, completed_oi = await self._get_bd_oi_windows(
                        symbol, dtn
                    )
                    if realtime_oi is None:
                        return False, None, None
                    oi_5m_last = realtime_oi[-1]
                    oi_peak = max(completed_oi)
                    passed = oi_5m_last <= oi_peak * (1 - self.BD_OI_DRAWDOWN_RATIO)
                    return (True, None, None) if passed else (False, None, None)

                # 多空人数比：1h序列按UTC小时缓存，5m那根按当前周期缓存
                lsr_1h = await self._get_lsr_1h_data(symbol, dtn)
                lsr_5m = await self._get_lsr_5m_data(symbol)
                if not lsr_1h or not lsr_5m:
                    return False, None, None

                lsrd = float(lsr_5m[0]["longShortRatio"])  # 当前值

                # 多仓比例提取：优先 longAccount，缺失时由 longShortRatio 推导
                def _extract_long_ratio(item):
                    long_account = item.get("longAccount")
                    if long_account is not None:
                        return float(long_account)
                    lsr = float(item["longShortRatio"])
                    return lsr / (1 + lsr)

                oi_5m = await self._get_oi_5m_data(symbol)

                if not oi_5m:
                    return False, None, None
                oi_5m_last = float(oi_5m[-1]["sumOpenInterest"])
                if positionSide == PositionSide.LONG.value:
                    oi_1h = await self._get_oi_history_data(symbol, dtn, "1h")

                    if not oi_1h:
                        return False, None, None
                    sum_open_interest_1h = [
                        float(item["sumOpenInterest"]) for item in oi_1h
                    ]
                    oi_hist_for_cheb = sum_open_interest_1h[
                        : -self.LONG_OI_CHEB_EXCLUDE_RECENT_COUNT
                    ]
                    if len(oi_hist_for_cheb) < self.MIN_CHEB_SAMPLE_SIZE:
                        return False, None, None

                    if oi_5m_last <= 0:
                        return False, None, None

                    # blend 基准：切比雪夫区间最后一根的OI和多仓比例（同一根）
                    # 两条1h序列独立更新缓存，末根可能错位，按时间戳配对
                    window_end_oi = oi_hist_for_cheb[-1]
                    window_end_ts = int(
                        oi_1h[-self.LONG_OI_CHEB_EXCLUDE_RECENT_COUNT - 1][
                            "timestamp"
                        ]
                    )
                    lsr_1h_by_ts = {int(item["timestamp"]): item for item in lsr_1h}
                    window_end_lsr = lsr_1h_by_ts.get(window_end_ts)
                    if window_end_lsr is None:
                        return False, None, None

                    window_end_long_ratio = _extract_long_ratio(window_end_lsr)
                    long_ratio_5m = _extract_long_ratio(lsr_5m[0])

                    blend = (
                        window_end_oi * window_end_long_ratio
                        + (oi_5m_last - window_end_oi)
                        * self.OI_DELTA_LONG_RATIO_WEIGHT
                    ) / oi_5m_last

                    if blend < long_ratio_5m:
                        return False, None, None

                    chebyshev = self.calculate_chebyshev_probability(
                        oi_hist_for_cheb,
                        oi_5m_last,
                    )
                    passed = (
                        oi_5m_last >= max(sum_open_interest_1h)
                        and chebyshev["chebyshev_upper_bound"]
                        < self.CHEBYSHEV_EXTREME_THRESHOLD
                    )
                    if not passed:
                        return False, None, None

                    oi_drawdown_threshold = oi_5m_last * (
                        1 - self.BZ_LONG_OI_DRAWDOWN_RATIO
                    )
                    chebyshev_one_percent_oi = chebyshev["mean"] + chebyshev[
                        "std"
                    ] / (self.CHEBYSHEV_EXTREME_THRESHOLD**0.5)
                    stop_guard_threshold = min(
                        oi_drawdown_threshold,
                        chebyshev_one_percent_oi,
                    )
                    return True, lsrd, stop_guard_threshold

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
                if not kline or len(kline) < self.KLINE_LIMIT:
                    return []
                # 将所有数据转换为浮点数格式
                return [list(map(float, sublist)) for sublist in kline]
            except Exception as e:
                self.logger.error(
                    f"{symbol}获取K线数据失败: {type(e).__name__}: {e!r}"
                )
                # 获取失败时返回空列表
                return []

    async def _get_lsr_1h_data(self, symbol: str, dtn: datetime):
        """缓存BZ做多所需的1h多空人数比，末根对上UTC小时边界就不拉。"""
        available_before_ts = self._utc_history_boundary_ms(dtn, "1h")

        cached = self._lsr_1h_cache.get(symbol)
        if cached and self._bar_timestamp_ms(cached[-1]) == available_before_ts:
            return cached

        try:
            data = await self._call_api(
                self.market_client.rest_api.long_short_ratio,
                symbol=symbol,
                period="1h",
                limit=self.LONG_SHORT_RATIO_LIMIT,
            )
        except Exception as e:
            self.logger.error(
                f"{symbol}获取1h多空比数据失败: {type(e).__name__}: {e!r}"
            )
            return self._lsr_1h_cache.get(symbol)

        available_lsr = [
            item
            for item in (data or [])
            if item.get("timestamp") is not None
            and int(item["timestamp"]) <= available_before_ts
        ]
        if len(
            available_lsr
        ) >= self.LONG_SHORT_RATIO_LIMIT and self._is_newer_bar(
            available_lsr[-1], cached
        ):
            self._lsr_1h_cache[symbol] = available_lsr
        return self._lsr_1h_cache.get(symbol)

    async def _get_lsr_5m_data(self, symbol: str):
        return await self._get_5m_data(
            symbol, self._lsr_5m_cache,
            self.market_client.rest_api.long_short_ratio, "多空比",
        )

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

        # Wilder's Smoothing (RMA)
        # 第一个 ATR 使用 SMA
        atr = sum(tr_list[:period]) / period
        # 之后使用指数平滑
        for i in range(period, len(tr_list)):
            atr = (atr * (period - 1) + tr_list[i]) / period

        hl2 = (kline_data[-1][2] + kline_data[-1][3]) / 2
        atr_cap = hl2 * self.ATR_HL2_CAP_RATIO
        return min(atr, atr_cap) if atr_cap > 0 else atr

    # 止盈止损计算辅助函数
    def calc_stop_profit_loss(self, price, is_long=True, atr=0):
        if atr <= 0:
            return (0, 0)

        take_profit_distance = atr * self.TAKE_PROFIT_ATR_FACTOR
        stop_loss_distance = atr * self.STOP_LOSS_ATR_FACTOR
        if is_long:
            return (
                price + take_profit_distance,
                price - stop_loss_distance,
            )
        else:
            # 做空：返回 (下界/止盈位, 上界/止损位)
            return (
                price - take_profit_distance,
                price + stop_loss_distance,
            )

    def calculate_chebyshev_probability(self, data_list, value):
        """保留 AUTOBN 的列表统计口径，复用概率计算。"""
        if not data_list:
            raise ValueError("数据列表不能为空")
        mean = sum(data_list) / len(data_list)
        std = (
            (sum((item - mean) ** 2 for item in data_list) / (len(data_list) - 1)) ** 0.5
            if len(data_list) > 1 else 0.0
        )
        return _chebyshev_result(mean, std, value)

    def _first_take_profit_target(self, entry_price, take_profit_gap, atr_value):
        atr_trigger = max(
            min(atr_value, entry_price * self.ATR_TRIGGER_CAP_RATIO),
            self.MIN_ATR_TRIGGER,
        )
        return min(take_profit_gap / self.TARGET_PROFIT_DIVISOR, atr_trigger)

    async def _close_triggered_position(
        self, symbol, close_info, atr_value, current_price
    ):
        is_long = close_info.position_side == PositionSide.LONG
        # 多头所有止盈阶段都只使用OI止损，价格止损仅对空头生效。
        if not is_long and current_price >= close_info.stop_loss:
            if not close_info.close_reason:
                close_info.close_reason = "初始止损"
            await self.close_bn_position(symbol, close_info, atr_value, current_price, 1)
            return True

        tp_triggered = (
            current_price >= close_info.take_profit
            if is_long else current_price <= close_info.take_profit
        )
        first_tp_triggered = False
        if close_info.tp_count < 1:
            direction = 1 if is_long else -1
            profit = (current_price - close_info.entry_price) * direction
            take_profit_gap = (close_info.take_profit - close_info.entry_price) * direction
            first_tp_target = self._first_take_profit_target(
                close_info.entry_price, take_profit_gap, atr_value
            )
            first_tp_triggered = (
                (first_tp_target > 0 and profit >= first_tp_target)
                or (is_long and tp_triggered)
            )

        if first_tp_triggered or tp_triggered:
            close_info.close_reason = "首次止盈" if first_tp_triggered else "止盈"
            await self.close_bn_position(
                symbol,
                close_info,
                atr_value,
                current_price,
                self.PARTIAL_CLOSE_RATIO,
                take_profit_stage="first" if first_tp_triggered else "regular",
            )
            return True

        if is_long and close_info.stop_guard_threshold > 0:
            oi_5m = await self._get_oi_5m_data(symbol)
            if oi_5m and float(oi_5m[-1]["sumOpenInterest"]) <= close_info.stop_guard_threshold:
                close_info.close_reason = "OI止损"
                await self.close_bn_position(symbol, close_info, atr_value, current_price, 1)
                return True
        return False

    async def _add_to_position(self, symbol, close_info, atr_value, is_long):
        close_info.strategy.append(PositionSide.DCA)
        opened = await self.open_bn_position(
            symbol,
            OrderSide.BUY.value if is_long else OrderSide.SELL.value,
            close_info.position_side.value,
            close_info.take_profit,
            close_info.stop_loss,
            close_info,
        )
        if not opened:
            close_info.strategy.pop()
            return

        amount_price = await self.get_amount_close(symbol)
        if amount_price is None:
            await self.send_msg(f"{symbol} 加仓后查询持仓均价失败")
        elif amount_price[1] > 0:
            close_info.entry_price = amount_price[1]
        # 加仓成功后再统计次数、使用新均价，不能复用开仓前的价格距离。
        dca_count = close_info.strategy.count(PositionSide.DCA)
        distance = atr_value * self.DCA_TP_ATR_RATIO**dca_count
        if is_long:
            close_info.take_profit = min(close_info.take_profit, close_info.entry_price + distance)
        else:
            close_info.take_profit = max(close_info.take_profit, close_info.entry_price - distance)

    def _decay_take_profit(self, close_info, atr_value, take_profit_rail, is_long):
        direction = 1 if is_long else -1
        take_profit_gap = (close_info.take_profit - close_info.entry_price) * direction
        decay_step = take_profit_gap * self.STOP_LOSS_DECAY_PER_MINUTE * (1 + close_info.tp_count)
        candidates = [close_info.take_profit - direction * decay_step, take_profit_rail]
        dca_count = close_info.strategy.count(PositionSide.DCA)
        if dca_count > 0:
            candidates.append(
                close_info.entry_price + direction * atr_value * self.DCA_TP_ATR_RATIO**dca_count
            )
        close_info.take_profit = (
            max(min(candidates), close_info.entry_price)
            if is_long else min(max(candidates), close_info.entry_price)
        )

    async def _manage_long_position(
        self, symbol, close_info, atr_value, current_price, take_profit_rail
    ):
        if current_price < close_info.entry_price - atr_value:
            await self._add_to_position(symbol, close_info, atr_value, is_long=True)
            return
        self._decay_take_profit(close_info, atr_value, take_profit_rail, is_long=True)

    async def _manage_short_position(
        self, symbol, close_info, atr_value, current_price, stop_loss_rail, take_profit_rail
    ):
        if current_price > close_info.entry_price + atr_value:
            await self._add_to_position(symbol, close_info, atr_value, is_long=False)
            return

        # 止损保护阈值使用衰减前的目标距离，保持原有执行顺序。
        take_profit_gap = close_info.entry_price - close_info.take_profit
        self._decay_take_profit(close_info, atr_value, take_profit_rail, is_long=False)
        profit = close_info.entry_price - current_price
        protect_profit = close_info.tp_count > 0 or profit >= self._first_take_profit_target(
            close_info.entry_price, take_profit_gap, atr_value
        )
        if protect_profit:
            candidate_stop = close_info.entry_price - profit * self.TRAILING_STOP_PROFIT_RATIO
            reason = "止盈后追踪止损" if close_info.tp_count > 0 else "追踪止损(保护盈利)"
        else:
            candidate_stop = stop_loss_rail
            reason = "移动止损(轨道)"
        new_stop_loss = min(close_info.stop_loss, candidate_stop)
        if new_stop_loss != close_info.stop_loss:
            close_info.stop_loss = new_stop_loss
            close_info.close_reason = reason

    async def _manage_position(self, symbol, close_info, kline, current_price):
        # 使用调用方提供的日K线，初始化和动态轨道共用同一份ATR计算。
        is_long = close_info.position_side == PositionSide.LONG
        atr_value = self.calculate_atr(kline)
        hl2 = (kline[-1][2] + kline[-1][3]) / 2
        if atr_value > 0:
            take_profit_rail, stop_loss_rail = self.calc_stop_profit_loss(
                hl2, is_long=is_long, atr=atr_value
            )
        else:
            # calc_stop_profit_loss在ATR无效时返回0；动态轨道原本落在中间价。
            take_profit_rail = stop_loss_rail = hl2
        if (close_info.take_profit == 0 or close_info.stop_loss == 0) and atr_value > 0:
            close_info.take_profit = take_profit_rail
            close_info.stop_loss = stop_loss_rail
            self.alert_all["POSITIONS"][symbol] = close_info.model_dump()
            self.logger.info(
                f"[ATR初始化] {symbol} 止盈:{close_info.take_profit:.2f} 止损:{close_info.stop_loss:.2f}"
            )

        if await self._close_triggered_position(symbol, close_info, atr_value, current_price):
            return

        if is_long:
            await self._manage_long_position(
                symbol, close_info, atr_value, current_price, take_profit_rail
            )
        else:
            await self._manage_short_position(
                symbol, close_info, atr_value, current_price, stop_loss_rail, take_profit_rail
            )
        self.alert_all["POSITIONS"][symbol] = close_info.model_dump()


    def _bd_market_matches(self, kline_close, kline_volume, *, refresh=False):
        """先用已有价格和成交量淘汰，不为不合格标的请求OI。"""
        if kline_close[-1] < max(kline_close[:-1]):
            return False
        volume_peak = max(kline_volume)
        if max(kline_volume[-self.BD_VOLUME_RECENT_COUNT :]) >= volume_peak:
            return False
        return refresh or max(
            kline_volume[-self.BD_VOLUME_LOOKBACK_COUNT : -self.BD_VOLUME_RECENT_COUNT]
        ) == volume_peak

    async def _is_bd_observation(
        self,
        symbol,
        kline_close,
        kline_volume,
        dtn,
        oi_window=None,
        refresh=False,
    ):
        """判断BD观察是否满足首次入池或刷新条件。"""
        if not self._bd_market_matches(kline_close, kline_volume, refresh=refresh):
            return False

        if oi_window is None:
            oi_window, _ = await self._get_bd_oi_windows(symbol, dtn)
        if oi_window is None or len(oi_window) < self.OI_QUERY_LIMIT:
            return False

        oi_baseline = oi_window[: -self.BD_OI_LOOKBACK_COUNT]
        oi_old = oi_window[
            -self.BD_OI_LOOKBACK_COUNT : -self.BD_OI_RECENT_COUNT
        ]
        oi_old_peak = max(oi_old)
        if oi_window[-1] <= oi_old_peak:
            return False
        if refresh:
            return True

        return (
            self.calculate_chebyshev_probability(oi_baseline, oi_old_peak)[
                "chebyshev_upper_bound"
            ]
            < self.SHORT_OI_CHEB_THRESHOLD
        )

    async def _build_open_signal(
        self, symbol, kline, current_price, open_info, is_long, long_short_ratio
    ):
        hl2 = (kline[-1][2] + kline[-1][3]) / 2
        atr_value = self.calculate_atr(kline)
        take_profit, stop_loss = self.calc_stop_profit_loss(
            hl2, is_long=is_long, atr=atr_value
        )
        if take_profit == 0 and stop_loss == 0:
            return None

        basis_rate = await self.get_basis_rate(symbol)
        basis_triggered = (
            basis_rate < -self.BASIS_RATE_THRESHOLD
            if is_long
            else basis_rate > self.BASIS_RATE_THRESHOLD
        )
        if basis_triggered:
            open_info.strategy.append(PositionSide.Basis)

        lsr_show = (
            f"{long_short_ratio:.4f}" if long_short_ratio is not None else "N/A"
        )
        rate_show = atr_value * self.TAKE_PROFIT_ATR_FACTOR / current_price
        strategy_tag = format_strategy_tags(open_info.strategy)
        msg = (
            f"==={symbol}**{strategy_tag}**===\n"
            f"价格:{current_price}\n"
            f"基差率:{basis_rate:.4%}\n"
            f"多空比:{lsr_show}\n"
            f"止盈:{take_profit}\n"
            f"止损:{stop_loss}\n"
            f"收益率:{rate_show:.2%}"
        )
        return take_profit, stop_loss, basis_rate, msg

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

            current_timestamp = dtn.timestamp()

            # 观察记录的冷却和超时只依赖本地状态，优先于行情请求处理
            if close_info is None and open_info:
                if open_info.is_reopen_cooldown_active(current_timestamp):
                    self.logger.info(f"{symbol} 仍在平仓冷却期，跳过开仓分析")
                    return

                observation_timeout = (
                    self.BZ_OBSERVATION_TIMEOUT_SECONDS
                    if PositionSide.BZ in open_info.strategy
                    else self.BD_OBSERVATION_TIMEOUT_SECONDS
                )
                if current_timestamp - open_info.timestamp > observation_timeout:
                    self.alert_all["OBSERVATIONS"].pop(symbol, None)
                    open_info = None

            # 获取日K线数据（30天）
            kline = await self.get_kline(semaphore, symbol, "1Dutc")
            # 数据量检查
            if len(kline) < self.KLINE_LIMIT:
                return
            success.add(symbol)
            kline_close = [k[4] for k in kline]
            kline_volume = [k[5] for k in kline]

            # 预计算常用值
            current_price = kline_close[-1]
            # 仅本轮复用：None尚未取数，空列表表示已取数但不可用；下轮重新获取。
            bd_oi_window = None

            # 检查现有持仓是否需要平仓
            if close_info:
                await self._manage_position(
                    symbol,
                    close_info,
                    kline,
                    current_price,
                )
            elif open_info:
                price_delta = current_price - kline_close[-2]
                is_long = price_delta > 0
                open_strategy = PositionSide.BZ if is_long else PositionSide.BD
                if price_delta != 0 and open_strategy in open_info.strategy:
                    position_side = PositionSide.LONG if is_long else PositionSide.SHORT
                    order_side = OrderSide.BUY if is_long else OrderSide.SELL
                    passed, long_short_ratio, stop_guard_threshold = await self.check_side(
                        semaphore, symbol, position_side.value, dtn
                    )
                    if passed:
                        signal = await self._build_open_signal(
                            symbol, kline, current_price, open_info,
                            is_long=is_long, long_short_ratio=long_short_ratio,
                        )
                        if signal is not None:
                            take_profit, stop_loss, basis_rate, open_signal = signal
                            open_info.side = order_side
                            order_result = await self.open_bn_position(
                                symbol, order_side.value, position_side.value,
                                take_profit, stop_loss, open_info, open_signal,
                            )
                            if not order_result:
                                return
                            close_info = Position(
                                take_profit=take_profit,
                                stop_loss=stop_loss,
                                close_side=OrderSide.SELL if is_long else OrderSide.BUY,
                                position_side=position_side,
                                entry_price=current_price,
                                name=symbol,
                                date=int(dtn.strftime("%Y%m%d")),
                                strategy=open_info.strategy,
                                stop_guard_threshold=(
                                    stop_guard_threshold
                                    if is_long and stop_guard_threshold is not None else 0.0
                                ),
                                long_short_ratio=(
                                    f"{long_short_ratio:.4f}" if long_short_ratio is not None else ""
                                ),
                                basis_rate=f"{basis_rate:.4%}",
                            )
                            self.alert_all["POSITIONS"][symbol] = close_info.model_dump()
                            open_info.strategy = [open_info.strategy[0]]
                            self.alert_all["OBSERVATIONS"][symbol] = open_info.model_dump()

                if not close_info and PositionSide.BD in open_info.strategy:
                    if kline_volume[-1] >= max(kline_volume[:-1]):
                        self.alert_all["OBSERVATIONS"].pop(symbol, None)
                        open_info = None
                    elif self._bd_market_matches(kline_close, kline_volume, refresh=True):
                        bd_oi_window, _ = await self._get_bd_oi_windows(symbol, dtn)
                        if bd_oi_window is None:
                            bd_oi_window = []
                        if await self._is_bd_observation(
                            symbol, kline_close, kline_volume, dtn,
                            oi_window=bd_oi_window, refresh=True,
                        ):
                            open_info.price = current_price
                            open_info.timestamp = current_timestamp
                            self.alert_all["OBSERVATIONS"][symbol] = open_info.model_dump()


            # 无论是否有仓位，都执行“加入观察”判定逻辑；本轮新观察覆盖旧记录
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

            # 做空信号判断；同轮做多信号优先
            elif await self._is_bd_observation(
                symbol, kline_close, kline_volume, dtn, oi_window=bd_oi_window
            ):
                new_open_info = Observation(
                    price=current_price,
                    timestamp=current_timestamp,
                    side=OrderSide.SELL,
                    strategy=[PositionSide.BD],
                    name=symbol,
                )
            if new_open_info:
                current_open_info_dict = self.alert_all["OBSERVATIONS"].get(symbol)
                if current_open_info_dict:
                    current_open_info = Observation.model_validate(
                        current_open_info_dict
                    )
                    new_open_info.earliest_open_timestamp = (
                        current_open_info.earliest_open_timestamp
                    )
                self.alert_all["OBSERVATIONS"][symbol] = new_open_info.model_dump()
        except Exception:
            success.discard(symbol)
            self.logger.exception(f"处理标的 {symbol} 时发生异常")
            return

    async def get_exchange_info(self):
        current_time = time.time()
        if (
            self._exchange_info_cache is not None
            and current_time - self._exchange_info_cache_timestamp
            < self.EXCHANGE_INFO_CACHE_TTL
        ):
            return self._exchange_info_cache
        exchange_info = await self._call_api(
            self.market_client.rest_api.exchange_information
        )
        self._exchange_info_cache = exchange_info
        self._exchange_info_cache_timestamp = current_time
        return exchange_info

    def get_symbols_info(self, exchange_info):
        # 先筛选交易对，再计算需要的精度；完成后一次更新元信息。
        symbols_info = {}
        for symbol in exchange_info["symbols"]:
            if "USDT" not in symbol["quoteAsset"] or "TRADING" not in symbol["status"]:
                continue
            quantity_precision = symbol["quantityPrecision"]
            symbols_info[symbol["symbol"]] = {
                "quotePrecision": symbol["quotePrecision"],
                "quantityPrecision": (
                    Decimal("1") if quantity_precision == 0
                    else Decimal(f"0.{'1' * quantity_precision}")
                ),
            }
        self.symbols_info = symbols_info

    def get_position_risk(self, position_risk=None):
        # 获取当前持仓信息，用于清理无效持仓
        position_risk = self._normalize_position_risk(position_risk)
        active_symbols = {position["symbol"] for position in position_risk}
        # 只保留当前有持仓的交易对记录
        self.alert_all["POSITIONS"] = {
            k: v
            for k, v in self.alert_all["POSITIONS"].items()
            if k in active_symbols
        }
        positions_data = []
        today = int(datetime.datetime.now().strftime("%Y%m%d"))
        for p in position_risk:
            entryPrice = float(p["entryPrice"])
            notional = abs(float(p.get("notional", 0) or 0))
            unrealized_profit = float(p.get("unRealizedProfit", 0) or 0)
            if notional == 0:
                self.logger.info(
                    f"跳过名义价值为0的持仓记录: symbol={p.get('symbol')} side={p.get('positionSide')}"
                )
                continue
            pos_data = self.alert_all["POSITIONS"].get(p["symbol"])
            if pos_data is not None:
                pos_obj = Position.model_validate(pos_data)
                pos_obj.entry_price = entryPrice
            else:
                is_long = p["positionSide"] == PositionSide.LONG.value
                pos_obj = Position(
                    take_profit=0,
                    stop_loss=0,
                    close_side=OrderSide.SELL if is_long else OrderSide.BUY,
                    position_side=PositionSide.LONG if is_long else PositionSide.SHORT,
                    entry_price=entryPrice,
                    name=p["symbol"],
                    date=today,
                    strategy=[PositionSide.N],
                )
            self.alert_all["POSITIONS"][p["symbol"]] = pos_obj.model_dump()
            positions_data.append(
                DailyPosition(
                    name=p["symbol"],
                    strategy=format_strategy_tags(pos_obj.strategy),
                    direction=p["positionSide"],
                    entry_price=entryPrice,
                    notional=notional,
                    unrealized_pnl=unrealized_profit,
                    profit_rate=unrealized_profit / notional,
                    take_profit=pos_obj.take_profit,
                    stop_loss=pos_obj.stop_loss,
                    open_date=pos_obj.date,
                    currency="USDT",
                )
            )

        return positions_data

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
        start_ts = time.time()
        try:
            self.logger.info(f"{market} 市场分析任务开始")
            await asyncio.wait_for(
                self._rzq_market_impl(market), timeout=self.MARKET_ANALYSIS_TIMEOUT
            )
            self.logger.info(
                f"{market} 市场分析任务结束，总耗时:{time.time() - start_ts:.2f}s"
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
        finally:
            # 成交链路只入队；扫描正常结束、异常或取消后统一刷盘。
            await CloseRecordManager.flush_pending_records()

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
                    exchange_info = await self.get_exchange_info()
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
            await self.send_msg(
                format_daily_positions_notification(
                    "AUTOBN",
                    "账户余额",
                    float(balance),
                    "USDT",
                    positions_data,
                ),
                channel="pushplus",
            )
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
    ATR_PERIOD = 5  # ATR计算周期：A股一周
    TAKE_PROFIT_ATR_FACTOR = 3.0  # AUTOA止盈价与止盈轨ATR倍数
    STOP_LOSS_ATR_FACTOR = 1.0  # AUTOA止损价与止损轨ATR倍数
    ATR_TRIGGER_CAP_RATIO = 0.05
    ATR_HL2_CAP_RATIO = 0.1  # ATR返回值上限比例（不超过hl2的10%）
    MIN_ATR_TRIGGER = 1e-8
    DCA_TP_ATR_RATIO = 0.5  # DCA触发后止盈收紧系数(按ATR与触发次数)

    # ==================== 切比雪夫概率阈值常量 ====================
    CHEBYSHEV_EXTREME_THRESHOLD = 0.01  # 极端异常阈值（1%）

    # ==================== 时间常量 ====================
    OBSERVATION_TIMEOUT_SECONDS = 30 * 24 * 60 * 60  # 观察记录超时时间（30天）

    # ==================== Trading Configuration ====================
    TRADING_DAYS_LOOKBACK = 20
    TAKE_PROFIT_DECAY = 0.001  # 每轮止盈距离衰减系数 (1‰)
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

    # ==================== 筛选常量 ====================
    DEFAULT_POSITION_SHARES = 100  # 单次开仓固定股数
    VOLUME_CHEB_SAMPLE_START_OFFSET = -20  # 成交量切比雪夫样本窗口起点（含）
    VOLUME_CHEB_SAMPLE_END_OFFSET = -5  # 成交量切比雪夫样本窗口终点（不含）
    VOLUME_CHEB_REQUIRED_HISTORY = 20  # 切片[-20:-5]所需最少历史K线数
    TARGET_PROFIT_DIVISOR = 3.0  # 目标收益分割系数（用于计算1/3收益触发点）

    DEFAULT_STATE_FILE = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "alert_all_A.json"
    )
    alert_all_file = None  # 显式 load_state 后才允许保存，导入模块不接触业务文件
    alert_all = {"POSITIONS": {}, "OBSERVATIONS": {}}
    _trading_calendar = None
    _calendar_loaded_on = None
    zt_dates = []
    hist_cache = {}
    _batch_window_id = None
    _batch_observations_snapshot = []
    _http_session = None
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

    # 状态显式加载与原子保存
    @classmethod
    def load_state(cls, filename=None):
        """程序启动时显式加载状态；加载失败不覆盖原文件。"""
        filename = os.fspath(filename or cls.DEFAULT_STATE_FILE)
        with open(filename, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
        if not isinstance(state, dict) or any(
            not isinstance(state.get(key, {}), dict)
            for key in ("POSITIONS", "OBSERVATIONS")
        ):
            raise ValueError("AUTOA 状态文件格式错误")
        state.setdefault("POSITIONS", {})
        state.setdefault("OBSERVATIONS", {})
        cls.alert_all = state
        cls.alert_all_file = filename
        cls.zt_dates = []
        cls.hist_cache = {}
        cls._batch_window_id = None
        cls._batch_observations_snapshot = []
        cls._trading_calendar = None
        cls._calendar_loaded_on = None

    @classmethod
    def save_state(cls):
        """先完整写临时文件，再原子替换，失败时保留原快照。"""
        if cls.alert_all_file is None:
            return
        filename = os.path.abspath(cls.alert_all_file)
        payload = json.dumps(cls.alert_all, ensure_ascii=False, indent=4)
        temporary_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=os.path.dirname(filename),
                prefix=os.path.basename(filename) + ".", suffix=".tmp", delete=False,
            ) as state_file:
                temporary_name = state_file.name
                state_file.write(payload)
                state_file.flush()
                os.fsync(state_file.fileno())
            os.replace(temporary_name, filename)
        finally:
            if temporary_name is not None and os.path.exists(temporary_name):
                os.remove(temporary_name)

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

        for i in range(len(hist_data) - period, len(hist_data)):
            h = float(highs[i])
            low_price = float(lows[i])
            pc = float(closes[i - 1])

            tr = max(h - low_price, abs(h - pc), abs(low_price - pc))
            tr_list.append(tr)

        atr = sum(tr_list) / period
        latest_high = float(highs[-1])
        latest_low = float(lows[-1])
        hl2 = (latest_high + latest_low) / 2
        atr_cap = hl2 * cls.ATR_HL2_CAP_RATIO
        return min(atr, atr_cap) if atr_cap > 0 else atr

    @classmethod
    def check_gap_up_after_bz_reference(
        cls, hist: pd.DataFrame, bz_reference_high: Optional[float]
    ) -> bool:
        """检查昨日回踩 BZ 基准后，今天是否跳空高开。"""
        if bz_reference_high is None or bz_reference_high <= 0:
            return False

        yesterday_low = float(hist.iloc[-2]["low"])
        today_open = float(hist.iloc[-1]["open"])
        yesterday_high = float(hist.iloc[-2]["high"])

        return yesterday_low < bz_reference_high and today_open > yesterday_high

    @classmethod
    def _update_bz_observation(cls, open_info: Observation, hist: pd.DataFrame) -> bool:
        """更新最近一次 BZ 以来的最低价，返回本轮是否触发 BZ，不改变持仓。"""
        if hist.empty:
            return False
        latest = hist.iloc[-1]
        current_low = float(latest["low"])
        if current_low <= 0 or pd.isna(current_low):
            return False
        if PositionSide.BZ in open_info.strategy:
            open_info.price = min(open_info.price, current_low)

        required_columns = {"open", "high", "close", "volume"}
        if (
            len(hist) < cls.VOLUME_CHEB_REQUIRED_HISTORY
            or not required_columns.issubset(hist.columns)
        ):
            return False
        if not (
            float(latest["close"]) > float(latest["open"])
            and float(latest["open"]) > float(hist.iloc[-2]["high"])
        ):
            return False
        hist_volume = hist["volume"].values
        current_volume = hist_volume[-1]
        volume_sample = hist_volume[
            cls.VOLUME_CHEB_SAMPLE_START_OFFSET : cls.VOLUME_CHEB_SAMPLE_END_OFFSET
        ]
        if not (
            current_volume >= max(hist_volume[cls.VOLUME_CHEB_SAMPLE_END_OFFSET :])
            and cls.calculate_chebyshev_probability(volume_sample, current_volume)[
                "chebyshev_upper_bound"
            ] < cls.CHEBYSHEV_EXTREME_THRESHOLD
        ):
            return False

        # 每次 BZ 都硬重置基准，即使旧的累计最低价更低。
        open_info.price = current_low
        open_info.bz_reference_high = float(hist.iloc[-2]["high"])
        if PositionSide.BZ not in open_info.strategy:
            open_info.strategy.append(PositionSide.BZ)
        return True

    @classmethod
    def calculate_chebyshev_probability(cls, data, value):
        """保留 AUTOA 的 pandas 样本统计口径，复用概率计算。"""
        series = data.iloc[:, 0] if isinstance(data, pd.DataFrame) else pd.Series(data)
        if series.empty:
            raise ValueError("数据不能为空")
        mean = float(series.mean())
        std = float(series.std(ddof=1)) if len(series) > 1 else 0.0
        return _chebyshev_result(mean, std, value)

    @classmethod
    async def _get_http_session(cls):
        if cls._http_session is None or cls._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=cls.HTTP_TIMEOUT_SECONDS)
            cls._http_session = aiohttp.ClientSession(timeout=timeout)
        return cls._http_session

    @classmethod
    async def close_http_session(cls):
        if cls._http_session is not None and not cls._http_session.closed:
            await cls._http_session.close()
        cls._http_session = None

    @classmethod
    async def send_msg(
        cls,
        msg: str | TradeNotification,
        *,
        channel: Literal["pushplus", "wecom"] | None = None,
    ):
        """按指定渠道发送 AUTOA 通知。"""
        try:
            log_message = msg.content if isinstance(msg, TradeNotification) else msg
            cls.logger.info(f"发送消息: {log_message}")
            if channel == "pushplus":
                if not isinstance(msg, TradeNotification):
                    cls.logger.warning("PushPlus 渠道需要 TradeNotification，跳过消息发送")
                    return
                try:
                    await send_pushplus(msg)
                except Exception as e:
                    cls.logger.error(f"PushPlus 消息发送异常: {str(e)}")
                return

            if channel == "wecom":
                if not isinstance(msg, str):
                    cls.logger.warning("企业微信渠道需要文本消息，跳过消息发送")
                    return
                webhook_key = os.getenv("AUTOA_WECOM_KEY", "")
                if not webhook_key:
                    cls.logger.warning("未配置 AUTOA_WECOM_KEY，跳过企业微信消息")
                    return
                json_msg = {"msgtype": "text", "text": {"content": msg}}
                http_session = await cls._get_http_session()
                try:
                    async with http_session.post(
                        url=(
                            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="
                            f"{webhook_key}"
                        ),
                        json=json_msg,
                    ) as response:
                        if response.status != 200:
                            response_text = await response.text()
                            cls.logger.error(
                                f"企业微信消息发送失败，状态码: {response.status}，响应: {response_text}"
                            )
                except Exception as e:
                    cls.logger.error(f"企业微信消息发送异常: {str(e)}")
                return

            if channel is not None:
                cls.logger.warning(f"未识别的消息渠道: {channel}")
        except Exception as e:
            cls.logger.error(f"消息发送异常: {str(e)}")

    @classmethod
    def _get_position_share_count(cls, close_info: Position) -> int:
        dca_count = close_info.strategy.count(PositionSide.DCA)
        return cls.DEFAULT_POSITION_SHARES * (1 + dca_count)

    @classmethod
    def _calculate_weighted_entry_price(
        cls, current_entry_price: float, open_price: float, existing_shares: int
    ) -> float:
        if current_entry_price <= 0 or existing_shares <= 0:
            return open_price
        total_cost = (
            current_entry_price * existing_shares
            + open_price * cls.DEFAULT_POSITION_SHARES
        )
        return total_cost / (existing_shares + cls.DEFAULT_POSITION_SHARES)

    @classmethod
    async def _get_sina_daily_bar(cls, code):
        """一次分时请求同时提供最新价和当日 OHLCV，失败时明确返回 None。"""
        symbol = ("sh" if code.startswith("6") else "sz") + code
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn/",
        }
        try:
            session = await cls._get_http_session()
            async with session.get(
                f"https://cn.finance.sina.com.cn/minline/getMinlineData?symbol={symbol}",
                headers=headers,
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
            rows = payload.get("result", {}).get("data", [])
            if not rows:
                return None
            intraday = pd.DataFrame(rows)
            if not {"p", "v", "tot_v"}.issubset(intraday.columns):
                return None
            for column in ("p", "v", "tot_v"):
                intraday[column] = pd.to_numeric(intraday[column], errors="coerce")
            intraday = intraday[intraday["p"].notna() & (intraday["p"] > 0)]
            if intraday.empty:
                return None
            prices = intraday["p"]
            total_volume = intraday.iloc[-1]["tot_v"]
            if pd.isna(total_volume):
                total_volume = intraday["v"].fillna(0).sum()
            return {
                "open": float(prices.iloc[0]),
                "high": float(prices.max()),
                "low": float(prices.min()),
                "close": float(prices.iloc[-1]),
                "volume": float(total_volume) / 100,
            }
        except Exception as error:
            cls.logger.warning(f"{code} 获取新浪分时行情失败: {error}")
            return None



    @classmethod
    def _calculate_position_valuation(
        cls, close_info: Position, current_price: float
    ) -> tuple[int, float, float, float]:
        position_shares = cls._get_position_share_count(close_info)
        notional = current_price * position_shares
        position_cost = close_info.entry_price * position_shares
        unrealized_pnl = notional - position_cost
        profit_rate = unrealized_pnl / position_cost if position_cost > 0 else 0.0
        return position_shares, notional, unrealized_pnl, profit_rate

    @classmethod
    async def push_daily_positions(cls):
        """每日推送一次A股策略持仓估值。"""
        try:
            positions = cls.alert_all.get("POSITIONS", {})
            if not positions:
                await cls.send_msg(
                    format_daily_positions_notification(
                        "AUTOA", "总持仓金额", 0, "CNY", []
                    ),
                    channel="pushplus",
                )
                return

            positions_data = []
            total_notional = 0.0
            for code, close_info_dict in list(positions.items()):
                close_info = Position.model_validate(close_info_dict)
                strategy_tag = format_strategy_tags(close_info.strategy)
                current_bar = await cls._get_sina_daily_bar(code)
                if current_bar is None:
                    positions_data.append(
                        DailyPosition(
                            name=f"{close_info.name}({code})",
                            strategy=strategy_tag,
                            direction=close_info.position_side.value,
                            entry_price=close_info.entry_price,
                            take_profit=close_info.take_profit,
                            stop_loss=close_info.stop_loss,
                            open_date=close_info.date,
                            currency="CNY",
                            price_decimals=2,
                            note="行情获取失败，暂不可估值（未计入总持仓金额）。",
                        )
                    )
                    continue

                current_price = current_bar["close"]
                position_shares, notional, unrealized_pnl, profit_rate = (
                    cls._calculate_position_valuation(close_info, current_price)
                )
                total_notional += notional
                positions_data.append(
                    DailyPosition(
                        name=f"{close_info.name}({code})",
                        strategy=strategy_tag,
                        direction=close_info.position_side.value,
                        entry_price=close_info.entry_price,
                        quantity=position_shares,
                        current_price=current_price,
                        notional=notional,
                        unrealized_pnl=unrealized_pnl,
                        profit_rate=profit_rate,
                        take_profit=close_info.take_profit,
                        stop_loss=close_info.stop_loss,
                        open_date=close_info.date,
                        currency="CNY",
                        price_decimals=2,
                    )
                )

            await cls.send_msg(
                format_daily_positions_notification(
                    "AUTOA",
                    "总持仓金额",
                    total_notional,
                    "CNY",
                    positions_data,
                ),
                channel="pushplus",
            )
        except Exception:
            cls.logger.exception("A股每日持仓推送失败")

    @classmethod
    async def _get_trading_calendar(cls):
        """同一天共用一份交易日历；请求失败保留可用缓存供退出后恢复冷却。"""
        loaded_on = datetime.date.today()
        if cls._trading_calendar is not None and cls._calendar_loaded_on == loaded_on:
            return cls._trading_calendar
        try:
            data = await asyncio.wait_for(
                asyncio.to_thread(ak.tool_trade_date_hist_sina),
                timeout=cls.AKSHARE_TIMEOUT_SECONDS,
            )
            dates = pd.to_datetime(data["trade_date"]).dropna().drop_duplicates().sort_values()
            if dates.empty:
                raise ValueError("交易日历为空")
            cls._trading_calendar = dates
            cls._calendar_loaded_on = loaded_on
        except Exception as error:
            cls.logger.error(f"获取交易日历失败: {error}")
        return cls._trading_calendar

    @classmethod
    async def get_last_trading_days(cls, today=None, days=None):
        """返回不晚于 today 的最近交易日，按降序排列。"""
        today = today or datetime.datetime.today()
        days = cls.TRADING_DAYS_LOOKBACK if days is None else days
        dates = await cls._get_trading_calendar()
        if dates is None:
            return []
        recent = dates[dates <= pd.Timestamp(today)].sort_values(ascending=False).iloc[:days]
        return [item.strftime("%Y-%m-%d") for item in recent]

    @classmethod
    async def get_following_trading_days(cls, today, days=2, *, calendar=None):
        """返回指定日期之后的实际交易日，与入池筛选共用日历。"""
        if calendar is None:
            calendar = await cls._get_trading_calendar()
        if calendar is None:
            return []
        following = calendar[calendar > pd.Timestamp(today).normalize()].iloc[:days]
        return [item.strftime("%Y-%m-%d") for item in following]

    @classmethod
    async def _get_reopen_timestamp_after_close(cls, today, *, calendar=None):
        following_days = await cls.get_following_trading_days(today, days=2, calendar=calendar)
        if len(following_days) < 2:
            return None
        return datetime.datetime.strptime(following_days[1], "%Y-%m-%d").timestamp()

    @classmethod
    async def stock_zh_a_hist(cls, code, start_date=None, end_date=None, frequency="d", adjustflag="3", *, require_current_day=False):
        """已完成历史 K 线加一根实时日 K；实时请求失败时不伪造最新价格。"""
        current_bar = await cls._get_sina_daily_bar(code)
        if current_bar is None:
            return pd.DataFrame()
        end_date = pd.Timestamp(end_date or datetime.date.today()).strftime("%Y-%m-%d")
        start_date = pd.Timestamp(start_date or "1970-01-01").strftime("%Y-%m-%d")
        cache_key = (code, start_date, end_date, frequency, adjustflag, require_current_day)
        try:
            if cache_key in cls.hist_cache:
                history = cls.hist_cache[cache_key]
            else:
                history = None
                for _ in range(2):
                    try:
                        history = await asyncio.wait_for(
                            asyncio.to_thread(
                                ak.stock_zh_a_hist, symbol=code,
                                period={"d": "daily", "w": "weekly", "m": "monthly"}.get(frequency, "daily"),
                                start_date=start_date.replace("-", ""),
                                end_date=end_date.replace("-", ""),
                                adjust={"3": "qfq", "2": "hfq", "1": ""}.get(adjustflag, "qfq"),
                            ),
                            timeout=cls.AKSHARE_TIMEOUT_SECONDS,
                        )
                        if history is not None and not history.empty:
                            break
                    except Exception:
                        history = None
                if history is None or history.empty:
                    return pd.DataFrame()
                history = history.rename(columns={
                    "日期": "date", "开盘": "open", "最高": "high",
                    "最低": "low", "收盘": "close", "成交量": "volume",
                })[["date", "open", "high", "low", "close", "volume"]].copy()
                for column in ("open", "high", "low", "close", "volume"):
                    history[column] = pd.to_numeric(history[column], errors="coerce")
                history = history.dropna(subset=["open", "high", "low", "close"])
                history_dates = pd.to_datetime(history["date"]).dt.normalize()
                target_date = pd.Timestamp(end_date)
                if require_current_day and not (history_dates == target_date).any():
                    return pd.DataFrame()
                history = history[history_dates < target_date]
                if history.empty:
                    return pd.DataFrame()
                cls.hist_cache[cache_key] = history
            today_row = {"date": end_date, **current_bar}
            return pd.concat([history, pd.DataFrame([today_row])], ignore_index=True)
        except Exception as error:
            cls.logger.error(f"{code} 获取股票历史数据失败: {error}")
            return pd.DataFrame()

    @classmethod
    async def _close_position(cls, code, close_info, price_close, today):
        """先完成退出状态和记录入队；重开日期延后确认，通知不能阻断退出。"""
        raw_observation = cls.alert_all["OBSERVATIONS"].get(code)
        open_info = (
            Observation.model_validate(raw_observation) if raw_observation else
            Observation(price=price_close, timestamp=today.timestamp(), side=OrderSide.BUY,
                        strategy=[], name=close_info.name)
        )
        open_info.earliest_open_timestamp = None
        open_info.reopen_pending_date = today.strftime("%Y-%m-%d")
        quantity = cls._get_position_share_count(close_info)
        entry_price = close_info.entry_price if close_info.entry_price > 0 else price_close
        profit_rate = price_close / entry_price - 1 if entry_price > 0 else 0
        realized_pnl = (price_close - entry_price) * quantity
        strategy_tag = format_strategy_tags(close_info.strategy)
        CloseRecordManager.enqueue_close(
            source="AUTOA", symbol=f"{close_info.name} {code}", position_side="LONG",
            entry_price=entry_price, close_price=price_close, close_amount=quantity,
            realized_pnl=realized_pnl, pnl_percent=profit_rate, close_ratio=1.0,
            strategy_tag=strategy_tag, close_reason=close_info.close_reason,
        )
        cls.alert_all["OBSERVATIONS"][code] = open_info.model_dump()
        cls.alert_all["POSITIONS"].pop(code, None)
        if PositionSide.N in close_info.strategy:
            msg = (
                f"{close_info.name} 平仓\n策略:{strategy_tag}\n"
                f"持仓方向:{close_info.position_side.value}\n委托价格:{price_close:.2f}\n"
                f"委托数量:{quantity}\n平仓盈亏:{realized_pnl:.2f} CNY\n"
                f"平仓收益:{profit_rate:.2%}\n平仓依据:{close_info.close_reason}"
            )
            await cls.send_msg(
                format_trade_notification("AUTOA", "平仓", close_info.name, msg),
                channel="pushplus",
            )

    @classmethod
    async def on_positions(cls, code, zt_dates, close_info_dict, today, *, exit_only=False):
        """刷新观察基准后管理持仓；N 止损固定，开仓当天不平仓或加仓。"""
        close_info = Position.model_validate(close_info_dict)
        hist = await cls.stock_zh_a_hist(
            code, start_date=zt_dates[-1], end_date=zt_dates[0], frequency="d", adjustflag="3",
            require_current_day=exit_only,
        )
        raw_observation = cls.alert_all["OBSERVATIONS"].get(code)
        if raw_observation:
            open_info = Observation.model_validate(raw_observation)
            cls._update_bz_observation(open_info, hist)
            cls.alert_all["OBSERVATIONS"][code] = open_info.model_dump()
        if int(today.strftime("%Y%m%d")) <= close_info.date:
            return
        if len(hist) < cls.VOLUME_CHEB_REQUIRED_HISTORY:
            return

        latest = hist.iloc[-1]
        price_close = float(latest["close"])
        prev_volume = float(hist.iloc[-2]["volume"])
        is_n = PositionSide.N in close_info.strategy
        if price_close >= close_info.take_profit:
            close_info.close_reason = "止盈"
        elif price_close <= close_info.stop_loss:
            close_info.close_reason = close_info.close_reason or "初始止损"
        elif not is_n and 0 < prev_volume <= close_info.stop_guard_threshold:
            close_info.close_reason = "成交量止损"
        else:
            atr = cls.calculate_atr(hist, period=cls.ATR_PERIOD)
            tp_gap = close_info.take_profit - close_info.entry_price
            atr_trigger = max(
                min(atr, close_info.entry_price * cls.ATR_TRIGGER_CAP_RATIO),
                cls.MIN_ATR_TRIGGER,
            )
            target_profit = min(tp_gap / cls.TARGET_PROFIT_DIVISOR, atr_trigger)
            profit = price_close - close_info.entry_price
            if tp_gap > 0 and profit >= target_profit:
                close_info.close_reason = "首次止盈"
            elif exit_only:
                return
            else:
                dca_count = close_info.strategy.count(PositionSide.DCA)
                dca_triggered = (
                    atr > 0 and close_info.entry_price > 0
                    and price_close < close_info.entry_price - atr
                )
                if dca_triggered:
                    existing_shares = cls.DEFAULT_POSITION_SHARES * (1 + dca_count)
                    close_info.entry_price = cls._calculate_weighted_entry_price(
                        close_info.entry_price, price_close, existing_shares,
                    )
                    close_info.strategy.append(PositionSide.DCA)
                    dca_count += 1
                    close_info.take_profit = min(
                        close_info.take_profit,
                        close_info.entry_price + atr * cls.DCA_TP_ATR_RATIO**dca_count,
                    )
                else:
                    hl2 = (float(latest["high"]) + float(latest["low"])) / 2
                    upper = hl2 + atr * cls.TAKE_PROFIT_ATR_FACTOR
                    next_tp = min(close_info.take_profit - tp_gap * cls.TAKE_PROFIT_DECAY, upper)
                    if dca_count:
                        next_tp = min(next_tp, close_info.entry_price + atr * cls.DCA_TP_ATR_RATIO**dca_count)
                    close_info.take_profit = max(next_tp, close_info.entry_price)
                    if not is_n:
                        new_stop_loss = max(close_info.stop_loss, hl2 - atr * cls.STOP_LOSS_ATR_FACTOR)
                        if new_stop_loss != close_info.stop_loss:
                            close_info.stop_loss = new_stop_loss
                            close_info.close_reason = "移动止损(轨道)"

                # 没有 await 的完整状态更新在先；通知取消也不会丢失 DCA。
                cls.alert_all["POSITIONS"][code] = close_info.model_dump()
                if dca_triggered and is_n:
                    strategy_tag = format_strategy_tags(close_info.strategy)
                    msg = (
                        f"{close_info.name} 加仓\n策略:{strategy_tag}\n"
                        f"委托价格:{price_close:.2f}\n止盈:{close_info.take_profit:.2f}\n"
                        f"止损:{close_info.stop_loss:.2f}"
                    )
                    await cls.send_msg(
                        format_trade_notification("AUTOA", "开仓", close_info.name, msg),
                        channel="pushplus",
                    )
                return
        await cls._close_position(code, close_info, price_close, today)

    @classmethod
    async def on_observations(cls, code, zt_dates, open_info_dict, today, *, calendar=None):
        """先处理冷却与 BZ/N 信号，确认开仓后再计算风控和保存状态。"""
        open_info = Observation.model_validate(open_info_dict)
        now = today.timestamp()
        if open_info.reopen_pending_date is not None:
            reopen_timestamp = await cls._get_reopen_timestamp_after_close(
                pd.Timestamp(open_info.reopen_pending_date).to_pydatetime(), calendar=calendar,
            )
            if reopen_timestamp is None:
                return
            open_info.earliest_open_timestamp = reopen_timestamp
            open_info.reopen_pending_date = None
            cls.alert_all["OBSERVATIONS"][code] = open_info.model_dump()
        if open_info.is_reopen_cooldown_active(now):
            return
        if now - open_info.timestamp > cls.OBSERVATION_TIMEOUT_SECONDS:
            cls.alert_all["OBSERVATIONS"].pop(code, None)
            return
        if datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date() == datetime.datetime.fromtimestamp(
            open_info.timestamp, datetime.timezone.utc
        ).date():
            return
        hist = await cls.stock_zh_a_hist(
            code, start_date=zt_dates[-1], end_date=zt_dates[0], frequency="d", adjustflag="3",
        )
        bz_triggered = cls._update_bz_observation(open_info, hist)
        cls.alert_all["OBSERVATIONS"][code] = open_info.model_dump()
        if len(hist) < cls.VOLUME_CHEB_REQUIRED_HISTORY:
            return
        latest = hist.iloc[-1]
        price_close = float(latest["close"])
        if price_close <= float(latest["open"]):
            return
        n_triggered = (
            not bz_triggered and PositionSide.BZ in open_info.strategy
            and cls.check_gap_up_after_bz_reference(hist, open_info.bz_reference_high)
        )
        if not (bz_triggered or n_triggered):
            return

        atr = cls.calculate_atr(hist, period=cls.ATR_PERIOD)
        if not (math.isfinite(atr) and atr > 0):
            return
        if n_triggered and PositionSide.N not in open_info.strategy:
            open_info.strategy.append(PositionSide.N)
        volume_sample = hist["volume"].values[
            cls.VOLUME_CHEB_SAMPLE_START_OFFSET : cls.VOLUME_CHEB_SAMPLE_END_OFFSET
        ]
        volume_guard_threshold = float(sum(volume_sample) / len(volume_sample))
        hl2 = (float(latest["high"]) + float(latest["low"])) / 2
        take_profit = hl2 + atr * cls.TAKE_PROFIT_ATR_FACTOR
        is_n = PositionSide.N in open_info.strategy
        stop_loss = open_info.price if is_n else hl2 - atr * cls.STOP_LOSS_ATR_FACTOR
        cls.alert_all["POSITIONS"][code] = Position(
            take_profit=take_profit, stop_loss=stop_loss, close_side=OrderSide.SELL,
            position_side=PositionSide.LONG, entry_price=price_close,
            name=open_info.name, date=int(today.strftime("%Y%m%d")),
            strategy=open_info.strategy, stop_guard_threshold=volume_guard_threshold,
        ).model_dump()
        cls.alert_all["OBSERVATIONS"][code] = open_info.model_dump()
        strategy_tag = format_strategy_tags(open_info.strategy)
        target_return = abs(take_profit - price_close) / price_close if price_close > 0 else 0
        msg = (
            f"==={open_info.name}**{strategy_tag}**===\n价格:{price_close:.2f}\n"
            f"止盈:{take_profit:.2f}\n止损:{stop_loss:.2f}\n收益率:{target_return:.2%}\n"
        )
        await cls.send_msg(msg, channel="wecom")
        if is_n:
            await cls.send_msg(
                format_trade_notification("AUTOA", "开仓", open_info.name, msg),
                channel="pushplus",
            )
    @classmethod
    async def _refresh_close_observations(cls, today):
        """收盘入池/刷新；统一由 filter_stocks 在处理结束后保存。"""
        zt_df = await asyncio.wait_for(
            asyncio.to_thread(ak.stock_zt_pool_em, date=today.strftime("%Y%m%d")),
            timeout=cls.AKSHARE_TIMEOUT_SECONDS,
        )
        selected = set()
        semaphore = asyncio.Semaphore(cls.MAX_CONCURRENT_REQUESTS)

        async def update_stock(code, name):
            async with semaphore:
                try:
                    hist = await cls.stock_zh_a_hist(
                        code, start_date=cls.zt_dates[-1], end_date=cls.zt_dates[0],
                        frequency="d", adjustflag="3",
                    )
                    if hist.empty:
                        return
                    existing = cls.alert_all["OBSERVATIONS"].get(code)
                    if existing:
                        open_info = Observation.model_validate(existing)
                        if PositionSide.BZ in open_info.strategy:
                            cls._update_bz_observation(open_info, hist)
                        open_info.timestamp = today.timestamp()
                    else:
                        open_info = Observation(
                            price=float(hist.iloc[-1]["close"]), timestamp=today.timestamp(),
                            side=OrderSide.BUY, strategy=[], name=name,
                        )
                        selected.add(name)
                    cls.alert_all["OBSERVATIONS"][code] = open_info.model_dump()
                except Exception as error:
                    cls.logger.error(f"{code} 收盘更新观察列表失败: {error}")

        await asyncio.gather(*(update_stock(code, name) for code, name in zt_df[["代码", "名称"]].values))
        cls.zt_dates.clear()
        cls.hist_cache.clear()
        return selected

    @classmethod
    async def _process_market_batch(cls, today, *, positions_only=False):
        """已有持仓每轮处理，观察标的按五分钟窗口分批。"""
        semaphore = asyncio.Semaphore(cls.MAX_CONCURRENT_REQUESTS)
        window_seconds = cls.BATCH_WINDOW_MINUTES * 60
        window_id = int(today.timestamp() // window_seconds)
        slot = today.minute % cls.BATCH_SLOT_COUNT

        if not positions_only and cls._batch_window_id != window_id:
            cls._batch_window_id = window_id
            cls._batch_observations_snapshot = sorted(
                [
                    code
                    for code in cls.alert_all["OBSERVATIONS"].keys()
                    if code not in cls.alert_all["POSITIONS"]
                ]
            )

        observation_snapshot = [] if positions_only else cls._batch_observations_snapshot
        batch_observation_codes = observation_snapshot[slot::cls.BATCH_SLOT_COUNT]
        position_symbols = list(cls.alert_all["POSITIONS"].keys())
        effective_symbols = list(dict.fromkeys(batch_observation_codes + position_symbols))

        cls.logger.info(
            f"A任务开始 - window:{window_id} slot:{slot}/{cls.BATCH_SLOT_COUNT} "
            f"快照数量:{len(observation_snapshot)} 批次数量:{len(batch_observation_codes)} "
            f"持仓数量:{len(position_symbols)} 实际处理数量:{len(effective_symbols)}"
        )

        success = set()
        date_window = cls.zt_dates if not positions_only else [
            today.strftime("%Y-%m-%d"),
            (today - datetime.timedelta(days=cls.TRADING_DAYS_LOOKBACK * 3)).strftime("%Y-%m-%d"),
        ]

        async def _run_symbol(code, calendar=None):
            async with semaphore:
                try:
                    close_info = cls.alert_all["POSITIONS"].get(code)
                    if close_info is not None:
                        await cls.on_positions(
                            code, date_window, close_info, today,
                            exit_only=positions_only,
                        )
                    elif not positions_only:
                        open_info = cls.alert_all["OBSERVATIONS"].get(code)
                        if open_info is None:
                            return
                        await cls.on_observations(code, date_window, open_info, today, calendar=calendar)
                    success.add(code)
                except Exception as e:
                    cls.logger.error(
                        f"{code} 处理失败，已跳过该标的: {type(e).__name__}: {e!r}"
                    )

        # 仅本批待确认冷却的观察需要日历；其等待不占行情并发槽位。
        pending_codes = {
            code for code in batch_observation_codes
            if code not in cls.alert_all["POSITIONS"]
            and cls.alert_all["OBSERVATIONS"].get(code, {}).get("reopen_pending_date") is not None
        }

        async def _run_pending_observations():
            calendar = await cls._get_trading_calendar()
            if calendar is None:
                return  # 本批不重复请求，待确认状态留给下一批重试。
            await asyncio.gather(*(
                _run_symbol(code, calendar)
                for code in batch_observation_codes if code in pending_codes
            ))

        tasks = [_run_symbol(code) for code in effective_symbols if code not in pending_codes]
        if pending_codes:
            tasks.append(_run_pending_observations())
        if tasks:
            await asyncio.gather(*tasks)
        cls.logger.info(
            f"A任务结束 - window:{window_id} slot:{slot}/{cls.BATCH_SLOT_COUNT} "
            f"批次成功数量:{len(success)}"
        )
        return set()

    @classmethod
    async def filter_stocks(cls):
        """按交易时间选择收盘刷新或盘中处理，结束或取消时保存已完成状态。"""
        today = datetime.datetime.today()
        clock = (today.hour, today.minute)
        if not (cls.MARKET_OPEN_HOUR, cls.MARKET_OPEN_MINUTE) <= clock <= (
            cls.MARKET_CLOSE_HOUR, cls.MARKET_CLOSE_MINUTE
        ):
            return set()
        today_str = today.strftime("%Y-%m-%d")
        if not cls.zt_dates or cls.zt_dates[0] != today_str:
            cls.zt_dates = await cls.get_last_trading_days(today)
            cls.hist_cache.clear()
            cls._batch_window_id = None
            cls._batch_observations_snapshot = []
            if cls.zt_dates and cls.zt_dates[0] != today_str:
                return set()
        try:
            if not cls.zt_dates:
                # 日历不可用只管理已有仓位，且要求历史接口确认当天有交易。
                return await cls._process_market_batch(today, positions_only=True)
            if today.hour == cls.MARKET_CLOSE_HOUR:
                return await cls._refresh_close_observations(today)
            return await cls._process_market_batch(today)
        finally:
            cls.save_state()

    @classmethod
    async def monitor_stocks(cls):
        """限制行情/通知等待时间，结束时将已入队的平仓记录刷盘。"""
        start_ts = time.time()
        try:
            selected = await asyncio.wait_for(cls.filter_stocks(), timeout=cls.MONITOR_TIMEOUT)
            cls.logger.info(f"A股监控完成，新增观察:{selected} 耗时:{time.time() - start_ts:.2f}s")
        except asyncio.TimeoutError:
            cls.logger.error(f"A股监控任务超时({cls.MONITOR_TIMEOUT}秒)")
        except Exception:
            cls.logger.exception("A股监控任务异常")
        finally:
            await CloseRecordManager.flush_pending_records()


def handle_exit_signal(signum, _frame):
    """处理系统退出信号，确保触发atexit"""
    signal_name = "SIGINT (Ctrl+C)" if signum == signal.SIGINT else "SIGTERM"
    logger = logging.getLogger("AUTOA")
    logger.info(f"接收到退出信号 {signal_name}, 准备退出...")
    # 调用 sys.exit(0) 会触发 atexit 注册的函数
    sys.exit(0)


async def main():
    """
    主函数：设置定时任务并启动调度器

    功能：配置并启动所有定时任务
    任务1：A股监控（交易时段执行）
    任务2：币安市场分析（每分钟执行）
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(os.path.dirname(current_dir), ".env"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    AUTOA.load_state()
    atexit.register(AUTOA.save_state)
    signal.signal(signal.SIGINT, handle_exit_signal)
    signal.signal(signal.SIGTERM, handle_exit_signal)

    autobn = AUTOBN.from_cfg(
        alert_all_file=os.path.join(current_dir, "alert_all.json"),
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
        minute=25,
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
    try:
        await stop_event.wait()  # 等待事件触发（实际不会发生）
    finally:
        for action in (lambda: scheduler.shutdown(wait=False), AUTOA.save_state):
            try:
                action()
            except Exception:
                logger.exception("退出时停止调度或保存状态失败，继续清理")
        results = await asyncio.gather(
            CloseRecordManager.flush_pending_records(),
            AUTOA.close_http_session(),
            autobn.close_http_session(),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                logger.error(f"退出清理失败: {result}")


if __name__ == "__main__":
    """
    程序入口：初始化配置并启动主程序

    功能：初始化所有必要的配置和客户端，然后启动主程序
    """
    logger = logging.getLogger("AUTOA")
    logger.info("autoBN启动")
    # 启动主程序（调度器在main函数中初始化）
    asyncio.run(main())
