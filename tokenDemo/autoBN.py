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
import akshare as ak
import baostock as bs
import pandas as pd
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from binance.um_futures import UMFutures
from pydantic import BaseModel

# ==================== 类型定义 ====================


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BZ = "BZ"
    BD = "BD"
    DK = "DK"
    Supertrend = "Supertrend"
    Grid = "Grid"


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


class AUTOBN:
    """币安期货自动交易类"""

    # ==================== 并发控制常量 ====================
    MAX_CONCURRENT_REQUESTS = 10  # 最大并发请求数

    # ==================== 时间常量 ====================
    OBSERVATION_TIMEOUT_SECONDS = 7 * 96 * 15 * 60  # 观察记录超时时间（约7天）
    RETRY_DELAY_SECONDS = 2  # 重试延迟（秒）
    CLOSE_RETRY_DELAY = 3  # 平仓重试延迟（秒）

    # ==================== K线相关常量 ====================
    KLINE_LIMIT = 96  # K线数据条数
    MIN_KLINE_FOR_ANALYSIS = 4  # 分析所需最小K线数量

    # ==================== 多空比相关常量 ====================
    LONG_SHORT_RATIO_LIMIT = 30  # 多空比数据查询数量限制
    LONG_SHORT_RATIO_CACHE_TTL = 900  # 多空比缓存过期时间（秒）
    LONG_SHORT_RATIO_BZ_MAX = 4 / 6  # BZ做多多空比上限
    OI_5M_CACHE_TTL = 300  # 5分钟持仓量缓存过期时间（秒）

    # ==================== ATR风控常量 ====================
    ATR_PERIOD = 10  # ATR计算周期
    SUPERTREND_FACTOR = 3.0  # ATR倍数，用于计算止盈止损和supertrend上下轨
    STOP_LOSS_DECAY_PER_MINUTE = 0.0001  # 每分钟止盈止损衰减比例 (0.01%)

    # ==================== 回溯周期常量 ====================
    LSR_LOOKBACK_PERIOD = 10  # 多空比切比雪夫计算回溯周期
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

    # ==================== 基差率常量 ====================
    BASIS_RATE_THRESHOLD = 0.02  # 基差率开仓阈值（2%）

    # ==================== 平仓相关常量 ====================
    PARTIAL_CLOSE_RATIO = 0.7  # 部分平仓比例 (止盈时使用)
    TRAILING_STOP_PROFIT_RATIO = 0.7  # 追踪止损盈利保护比例 (保护70%盈利，允许30%回撤)
    MIN_NOTIONAL = 10  # 最小交易金额 (USDT)

    # ==================== 任务控制常量 ====================
    MAX_RETRY_COUNT = 10  # 最大重试次数
    EARLY_MORNING_HOUR = 8  # 早盘检测小时
    MARKET_ANALYSIS_TIMEOUT = 300  # 市场分析超时时间（秒）

    # ==================== 交易配置常量 ====================
    DEFAULT_LEVERAGE = 5  # 默认杠杆倍数
    DEFAULT_HEALTH_THRESHOLD = 70  # 默认健康度阈值（%）

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

        # 初始化币安期货客户端
        obj.um_futures_client = UMFutures(key=api_key, secret=api_secret)

        # 加载持仓记录
        with open(obj.alert_all_file, "r") as f:
            obj.alert_all = json.load(f)

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

        # 注册退出处理函数,在脚本退出时保存数据
        def save_on_exit():
            """脚本退出时保存alert_all数据到文件"""
            try:
                obj.logger.info(f"脚本退出,正在保存BN数据到 {obj.alert_all_file}...")
                with open(obj.alert_all_file, "w") as f:
                    json.dump(obj.alert_all, f, ensure_ascii=False, indent=4)
                obj.logger.info("BN数据保存完成")
            except Exception as e:
                obj.logger.error(f"保存BN数据失败: {str(e)}")
                obj.logger.exception("保存BN数据时发生异常")

        atexit.register(save_on_exit)

        return obj

    def send_msg(self, msg: str, wx: bool = False) -> None:
        """
        发送消息通知函数

        功能：通过企业微信或微信发送交易通知消息

        参数：
            msg: 要发送的消息内容
            wx: 是否使用微信发送（True=微信，False=企业微信）

        返回：
            None
        """
        try:
            self.logger.info(f"发送消息: {msg}")

            if wx:
                # 微信发送格式：使用微信API接口
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
                response = session.post(
                    f"http://wechatpadpro:1238/message/SendTextMessage?key={self.wx_key}",
                    json=json_msg,
                )
            else:
                # 企业微信发送格式：使用企业微信机器人webhook
                json_msg = {"msgtype": "text", "text": {"content": msg}}
                response = session.post(
                    url=f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={self.qy_key}",
                    json=json_msg,
                )

            # 检查发送结果，失败时记录状态码
            if response.status_code != 200:
                self.logger.error(f"消息发送失败，状态码: {response.status_code}")
        except Exception as e:
            # 异常处理：记录错误但不中断程序运行
            self.logger.error(f"消息发送异常: {str(e)}")

    def calculate_health_bn(self, notional) -> int:
        """
        计算币安账户健康度

        功能：评估“账户级”风险水平，作为全局兜底指标（与逐仓单个仓位无直接对应）
        原理：健康度 = (1 - 维持保证金总额/账户总余额) * 100%
        说明：逐仓仓位的维保同样计入维持保证金，但逐仓强平风险需另行计算
        参数：
            notional: 新增头寸的名义价值（USDT）
        返回：
            健康度百分比（0-100），100表示最健康，0表示已爆仓
        """
        # 获取账户基本信息
        account_data = self.um_futures_client.account()
        total_balance = float(account_data["totalMarginBalance"])  # 账户总余额

        # 获取所有持仓信息
        position_data = self.um_futures_client.get_position_risk()
        total_maintenance_margin = 0.0  # 维持保证金总额

        # 计算现有持仓的维持保证金
        for position in position_data:
            if float(position["positionAmt"]) != 0:  # 只计算有持仓的合约
                maintenance_margin = float(
                    position["maintMargin"]
                )  # 单个持仓的维持保证金
                total_maintenance_margin += maintenance_margin

        # 加上新增头寸的维持保证金
        total_maintenance_margin += notional * self.MAINTENANCE_MARGIN_RATE

        # 计算健康度
        if total_maintenance_margin == 0 and total_balance >= 0:
            return 100  # 无持仓且余额为正，最健康状态
        elif total_balance <= 0:
            return 0  # 余额为负，已爆仓
        else:
            # 健康度 = (1 - 维持保证金/总余额) * 100%，限制在0-100之间
            return round(
                min(100, max(0, (1 - total_maintenance_margin / total_balance) * 100))
            )

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
            # 获取所有持仓信息，转换为字典格式
            # positionAmt: 持仓数量（正数=多头，负数=空头）
            # 使用abs()取绝对值，统一处理多空持仓
            position_risk = await asyncio.to_thread(
                self.um_futures_client.get_position_risk
            )
            position = {
                k["symbol"]: [abs(float(k["positionAmt"])), float(k["entryPrice"])]
                for k in position_risk
            }
            return position.get(symbol, [0, 0])  # 返回指定交易对的持仓数量
        except Exception:
            # 异常时返回0，避免程序崩溃
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
            # 并行获取账户数据和标记价格（优化：减少API延迟）
            account_data, mark_price_data = await asyncio.gather(
                asyncio.to_thread(self.um_futures_client.account),
                asyncio.to_thread(self.um_futures_client.mark_price, symbol),
            )

            balance = float(account_data["availableBalance"])
            # 风险控制：检查可用余额
            if balance <= 0:
                self.send_msg(f"{symbol} 开仓失败：可用余额为零")
                return None

            if not mark_price_data:
                self.send_msg(f"{symbol} 开仓失败：无法获取标记价格")
                return None

            markPrice = float(mark_price_data["markPrice"])

            # 风险控制：检查交易对配置是否存在
            if symbol not in self.symbols_info:
                self.send_msg(f"{symbol} 开仓失败：找不到交易对信息")
                return None

            # ==================== 风险定仓位计算 ====================
            # 公式: 开仓数量 = (止损仓位 + 止盈仓位) / 2
            # 止损仓位 = (账户余额 * 风险比例) / |入场价 - 止损价|
            # 止盈仓位 = (账户余额 * 盈利比例) / |止盈价 - 入场价|
            if stop_loss_price is None or stop_loss_price <= 0:
                self.send_msg(f"{symbol} 开仓失败：未提供有效止损价格")
                return None
            if take_profit_price is None or take_profit_price <= 0:
                self.send_msg(f"{symbol} 开仓失败：未提供有效止盈价格")
                return None

            stop_loss_gap = abs(markPrice - stop_loss_price)
            take_profit_gap = abs(take_profit_price - markPrice)

            if stop_loss_gap <= 0 or take_profit_gap <= 0:
                self.send_msg(f"{symbol} 开仓失败：止损/止盈距离为零")
                return None

            total_balance = float(account_data["totalWalletBalance"])
            # 计算风险金额和目标盈利金额
            risk_amount = total_balance * self.RISK_PER_TRADE
            target_profit = total_balance * self.TARGET_PROFIT_RATIO

            # 按止损和止盈分别计算仓位，取均值
            amount_by_sl = risk_amount / stop_loss_gap
            amount_by_tp = target_profit / take_profit_gap
            amount_raw = (amount_by_sl + amount_by_tp) / 2

            # 安全兜底：持仓名义价值(算上杠杆后)不超过账户的 MAX_POSITION_RATIO
            # 例: 账户1000U, MAX=50% -> 最大开仓名义价值 500U
            max_notional = balance * self.MAX_POSITION_RATIO
            max_amount = max_notional / markPrice
            if amount_raw > max_amount:
                self.logger.warning(
                    f"{symbol} 风险仓位 {amount_raw:.4f} 超限，限制为 {max_amount:.4f}"
                )
                amount_raw = max_amount

            # 按交易对精度要求调整数量（向下取整，避免超出可用余额）
            amount = float(
                Decimal(str(amount_raw)).quantize(
                    self.symbols_info.get(symbol)["quantityPrecision"],
                    rounding=ROUND_DOWN,
                )
            )

            # 计算名义价值（用于风险控制）
            notional = amount * markPrice

            # 最小交易额检查
            if notional < self.MIN_NOTIONAL:
                # self.send_msg(
                #     f"{symbol} 开仓失败：交易额 {notional} 低于最小要求 {self.MIN_NOTIONAL} USDT"
                # )
                return None

            # 保证金充足性检查：确保所需保证金不超过可用余额
            required_margin = notional / self.leverage
            if required_margin > balance:
                # self.send_msg(
                #     f"{symbol} 开仓失败：所需保证金 {required_margin:.2f} 超过可用余额 {balance:.2f}"
                # )
                return None

            # 风险控制：检查"账户级健康度"（逐仓建议额外结合仓位强平距离/保证金冗余）
            # 健康度 = (1 - 维持保证金/总余额) * 100%
            # 目的：确保开仓后不会导致全局账户风险过高
            account_health = self.calculate_health_bn(notional)
            if account_health < self.health4open:
                # self.send_msg(
                #     f"{symbol} 开仓失败：预计健康度 {account_health}% 低于要求 {self.health4open}%"
                # )
                return None

            # 设置杠杆倍数 (异步)
            leverage_result = await asyncio.to_thread(
                self.um_futures_client.change_leverage,
                symbol=symbol,
                leverage=self.leverage,
            )
            actual_leverage = leverage_result.get("leverage", self.leverage)

            # 执行市价单开仓 (异步)
            tx = await asyncio.to_thread(
                self.um_futures_client.new_order,
                symbol=symbol,
                side=side,  # 'BUY'或'SELL'
                type="MARKET",  # 市价单，立即成交
                quantity=amount,  # 开仓数量
                positionSide=positionSide,  # 'LONG'或'SHORT'
            )
            # 发送成功通知
            # 提示：逐仓模式下本次下单会并入同一方向同一 symbol 的逐仓仓位，逐仓保证金与强平价随之重算
            rate_show = abs(take_profit_price - markPrice) / markPrice
            msg = f"{symbol} 开仓\n策略:{','.join([ps.value for ps in open_info.strategy])}\n持仓方向:{positionSide}\n杠杆:{actual_leverage}x\n委托数量:{tx.get('origQty', 0)}\n委托价格:{markPrice}\n名义价值:{notional} USDT\n账户余额:{total_balance:.2f}\n仓位比例:{notional / total_balance:.2%}\n收益率:{rate_show:.2%}"
            self.send_msg(msg)
            return account_data
        except Exception as e:
            # 异常处理：记录错误并发送通知
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
        # 获取当前持仓数量 (异步)
        amount_price = await self.get_amount_close(symbol)
        amount = amount_price[0]
        if not amount:  # 0表示无持仓
            return
        close_ratio = (
            1 if amount * close_ratio * price_close < self.MIN_NOTIONAL else close_ratio
        )
        # 计算实际平仓数量
        close_amount = amount * close_ratio
        close_amount = float(
            Decimal(str(close_amount)).quantize(
                self.symbols_info.get(symbol)["quantityPrecision"], rounding=ROUND_DOWN
            )
        )
        # 如果平仓数量为0，直接返回
        if close_amount <= 0:
            self.alert_all["POSITIONS"].pop(symbol)
            return
        side = close_info.close_side.value
        positionSide = close_info.position_side.value
        # 循环平仓，直到完全平仓或失败
        while close_amount > 0:
            try:
                # 执行市价单平仓 (异步)
                tx = await asyncio.to_thread(
                    self.um_futures_client.new_order,
                    symbol=symbol,
                    side=side,  # 平仓方向
                    type="MARKET",  # 市价单，立即成交
                    quantity=close_amount,  # 平仓数量
                    positionSide=positionSide,  # 持仓方向
                )
                # 尝试获取开仓价格，使用 close_info 对象的 entry_price
                entryPrice = (
                    amount_price[1] if amount_price[1] > 0 else close_info.entry_price
                )

                # 发送成功通知
                price_diff = (
                    price_close - entryPrice
                    if positionSide == PositionSide.LONG.value
                    else entryPrice - price_close
                )
                realized_pnl = price_diff * close_amount
                pnl_percent = price_diff / entryPrice if entryPrice != 0 else 0
                strategy_tag = ",".join([ps.value for ps in close_info.strategy])
                msg = f"{symbol} 平仓\n策略:{strategy_tag}\n持仓方向:{positionSide}\n委托价格:{price_close}\n委托数量:{tx.get('origQty', 0)}\n平仓比例:{close_ratio:.2%}\n平仓盈亏:{realized_pnl} USDT\n平仓收益:{pnl_percent:.2%}\n止盈次数:{close_info.tp_count}"
                self.send_msg(msg)

                # 记录平仓到Excel
                CloseRecordManager.record_close(
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
                )

                # 检查平仓后是否仍有该symbol的仓位，若无则从POSITIONS中移除 (异步)
                remaining_amount_price = await self.get_amount_close(symbol)
                remaining_amount = remaining_amount_price[0]
                if remaining_amount == 0 and symbol in self.alert_all["POSITIONS"]:
                    self.alert_all["POSITIONS"].pop(symbol)
                elif atr_value > 0:
                    is_long = positionSide == PositionSide.LONG.value
                    # 更新止盈止损并持久化到字典
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
                return symbol  # 成功平仓，退出循环
            except Exception:
                # 平仓失败，等待后重试 (异步)
                await asyncio.sleep(self.CLOSE_RETRY_DELAY)
                self.logger.exception(f"平仓 {symbol} 失败，当前价格: {price_close}")
                msg = f"bn平仓{symbol}失败，当前价格:{price_close}"
                self.send_msg(msg)
                # 重新获取持仓数量，可能部分平仓成功 (异步)
                current_amount_price = await self.get_amount_close(symbol)
                close_amount = current_amount_price[0] * close_ratio
                close_amount = float(
                    Decimal(str(close_amount)).quantize(
                        self.symbols_info.get(symbol)["quantityPrecision"],
                        rounding=ROUND_DOWN,
                    )
                )
        return None

    async def check_trend(
        self,
        semaphore,
        symbol,
        kline_data=None,
    ):
        """
        检查趋势信号 - 基于 Supertrend 指标

        功能: 使用 Supertrend 指标判断市场趋势方向
        参数:
            semaphore: 异步信号量
            symbol: 交易对符号
            kline_data: K线数据(可选,如果不提供则获取)
        返回:
            'LONG': 做多趋势
            'SHORT': 做空趋势
            0: 无明确趋势或数据不足
        """
        async with semaphore:
            try:
                # 获取 4 小时 K 线数据(如果未提供)
                if kline_data is None:
                    kline_data = await self.get_kline(semaphore, symbol, "15m")
                    if (
                        len(kline_data) < self.ATR_PERIOD + 1
                    ):  # 至少需要 ATR周期+1 根K线
                        return 0

                # 计算 Supertrend
                supertrend_values, directions = self.calculate_trend(
                    kline_data,
                    factor=self.SUPERTREND_FACTOR,
                    atr_period=self.ATR_PERIOD,
                )

                # 获取最近两根K线的方向
                if len(directions) < 2:
                    return 0

                prev_direction = directions[-2]
                curr_direction = directions[-1]

                # 检测趋势变化
                # 从下降趋势转为上升趋势: prev_direction=1, curr_direction=-1
                if prev_direction == 1 and curr_direction == -1:
                    return PositionSide.LONG.value  # 做多信号
                # 从上升趋势转为下降趋势: prev_direction=-1, curr_direction=1
                elif prev_direction == -1 and curr_direction == 1:
                    return PositionSide.SHORT.value  # 做空信号
                else:
                    # 趋势未变化,返回当前趋势方向
                    return 0

            except Exception:
                self.logger.exception("检查趋势信号时发生错误")
                return 0

    async def check_side(
        self,
        semaphore,
        symbol,
        positionSide,
        kline_close=None,
        kline_volume=None,
        dtn: datetime = None,
    ):
        """
        检查增仓信号，判断是否适合开仓
        """
        async with semaphore:
            try:
                # 获取多空人数比数据（使用缓存）
                long_short_ratio_data = await self.get_long_short_ratio(symbol)
                # 提取最新的多空人数比
                if not long_short_ratio_data:
                    return False

                # 提取所有历史多空比值
                lsr_values = [
                    float(item["longShortRatio"]) for item in long_short_ratio_data
                ]
                lsrd = lsr_values[-1]  # 当前值

                # 根据持仓方向判断多空比条件（极值逻辑）
                if positionSide == PositionSide.LONG.value:
                    if lsrd > self.LONG_SHORT_RATIO_BZ_MAX:
                        return False
                    # 做多：要求当前多空比是历史最低值（散户最恐慌）
                    if lsrd == min(lsr_values) and (
                        self.calculate_chebyshev_probability(
                            lsr_values[: -self.LSR_LOOKBACK_PERIOD],
                            lsrd,
                        )["chebyshev_upper_bound"]
                        < self.CHEBYSHEV_EXTREME_THRESHOLD
                    ):
                        return True
                    return False
                elif positionSide == PositionSide.SHORT.value:
                    # 做空：要求当前多空比是历史最高值（散户最疯狂）
                    if lsrd != max(lsr_values):
                        return False

                # 获取持仓量历史数据（带缓存）
                dtn_target = dtn.replace(hour=8, minute=0, second=0, microsecond=0)
                target_ts = int(dtn_target.timestamp() * 1000)

                # 检查缓存是否存在且有效（target_date 匹配当天8点）
                cache_entry = self._oi_1d_cache.get(symbol)
                if cache_entry and cache_entry.get("target_date") == target_ts:
                    # 缓存有效，直接使用
                    oi_1d = cache_entry["data"]
                else:
                    # 缓存无效或不存在，获取新数据
                    oi_1d = await asyncio.to_thread(
                        self.um_futures_client.open_interest_hist,
                        symbol=symbol,
                        period="1d",
                        limit=self.OI_QUERY_LIMIT,
                    )
                    # 检查数据是否满足条件
                    if oi_1d[-1]["timestamp"] != target_ts:
                        return False
                    # 数据满足条件，缓存起来
                    self._oi_1d_cache[symbol] = {
                        "data": oi_1d,
                        "target_date": target_ts,
                    }
                sumOpenInterestValue_1d = [
                    float(i["sumOpenInterestValue"]) for i in oi_1d
                ]  # 持仓价值（美元）
                sumOpenInterest_1d = [
                    float(i["sumOpenInterest"]) for i in oi_1d
                ]  # 持仓数量（合约数）

                # 做空条件检查：需要持仓量减少且多空比小于1（空头占优）
                # 条件1：最新持仓量必须小于前3天最小值（说明有资金流出）
                return any(
                    (
                        kline_close[index - 1] == max(kline_close)
                        and sumOpenInterestValue_1d[index]
                        == max(sumOpenInterestValue_1d)
                        and kline_close[-2] > max(kline_close[-4:-2])
                        and sumOpenInterestValue_1d[-1]
                        > max(sumOpenInterestValue_1d[-3:-1])
                        and max(kline_volume[-3:-1]) == max(kline_volume)
                        and sumOpenInterest_1d[-1] < sumOpenInterest_1d[-2]
                    )
                    for index in range(-1, max(-self.OI_LOOKBACK_PERIOD, -len(kline_close)), -1)
                )
            except Exception:
                self.logger.exception("检查增仓信号时发生错误")
                return False

    async def check_oi(self, semaphore, symbol, open_info, dtn):
        async with semaphore:
            try:
                current_time = time.time()
                oi_5m_cache = self._oi_5m_cache.get(symbol)
                if (
                    oi_5m_cache
                    and (current_time - oi_5m_cache["timestamp"]) < self.OI_5M_CACHE_TTL
                ):
                    oi_5m = oi_5m_cache["data"]
                else:
                    oi_5m = await asyncio.to_thread(
                        self.um_futures_client.open_interest_hist,
                        symbol=symbol,
                        period="5m",
                        limit=self.OI_QUERY_LIMIT,
                    )
                    self._oi_5m_cache[symbol] = {
                        "data": oi_5m,
                        "timestamp": current_time,
                    }

                # 获取 1h 持仓量数据（复用 _oi_1h_cache，需检查 target_date）
                dtn_target = dtn.replace(minute=0, second=0, microsecond=0)
                target_ts = int(dtn_target.timestamp() * 1000)

                oi_1h_cache = self._oi_1h_cache.get(symbol)
                if oi_1h_cache and oi_1h_cache.get("target_date") == target_ts:
                    oi_1h = oi_1h_cache["data"]
                else:
                    oi_1h = await asyncio.to_thread(
                        self.um_futures_client.open_interest_hist,
                        symbol=symbol,
                        period="1h",
                        limit=self.OI_QUERY_LIMIT,
                    )
                    # 如果数据时间戳匹配，也更新缓存
                    if oi_1h and oi_1h[-1]["timestamp"] == target_ts:
                        self._oi_1h_cache[symbol] = {
                            "data": oi_1h,
                            "target_date": target_ts,
                        }

                sumOpenInterestValue_5m = [
                    float(i["sumOpenInterestValue"]) for i in oi_5m
                ]  # 持仓价值（美元）
                sumOpenInterest_5m = [
                    float(i["sumOpenInterest"]) for i in oi_5m
                ]  # 持仓数量（合约数）

                sumOpenInterestValue_1h = [
                    float(i["sumOpenInterestValue"]) for i in oi_1h
                ]  # 持仓价值（美元）
                sumOpenInterest_1h = [
                    float(i["sumOpenInterest"]) for i in oi_1h
                ]  # 持仓数量（合约数）

                if PositionSide.BZ in open_info.strategy and (
                    sumOpenInterest_5m[-1] <= max(sumOpenInterest_1h)
                    or sumOpenInterestValue_5m[-1] <= max(sumOpenInterestValue_1h)
                ):
                    return False
                elif (
                    PositionSide.BD in open_info.strategy
                    and sumOpenInterest_5m[-1] >= sumOpenInterest_1h[-1]
                ):
                    return False
                return True
            except Exception:
                self.logger.exception("检查OI信号时发生错误")
                return False

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
                kline = await asyncio.to_thread(
                    self.um_futures_client.klines,
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
                data = await asyncio.to_thread(
                    self.um_futures_client.long_short_account_ratio,
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
            data2 = await asyncio.to_thread(
                self.um_futures_client.long_short_account_ratio,
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
        获取指定交易对的基差率

        基差率 = (期货价格 - 指数价格) / 指数价格
        - 基差率 > 0：期货升水（期货价格高于现货）
        - 基差率 < 0：期货贴水（期货价格低于现货）

        参数:
            symbol: 交易对符号，如'BTCUSDT'
        返回:
            基差率（浮点数），获取失败返回0
        """
        try:
            # 获取指数价格和标记价格
            premium_index = await asyncio.to_thread(
                self.um_futures_client.mark_price, symbol
            )
            if not premium_index:
                return 0.0

            index_price = float(premium_index.get("indexPrice", 0))
            mark_price = float(premium_index.get("markPrice", 0))

            if index_price <= 0:
                return 0.0

            # 基差率 = (期货价格 - 指数价格) / 指数价格
            basis_rate = (mark_price - index_price) / index_price
            return basis_rate
        except Exception as e:
            self.logger.error(f"{symbol} 获取基差率失败: {str(e)}")
            return 0.0

    def calculate_trend(self, kline_data, factor=3.0, atr_period=10):
        """
        计算 Supertrend 指标

        参数:
            kline_data: K线数据列表
            factor: 因子，默认3.0
            atr_period: ATR周期，默认10

        返回:
            (supertrend_values, directions): supertrend值列表和方向列表
            方向: -1 表示上升趋势, 1 表示下降趋势
        """
        if not kline_data or len(kline_data) < atr_period + 1:
            return [], []

        supertrend_values = []
        directions = []

        # 预计算所有 TR 值
        tr_list = []
        for i in range(1, len(kline_data)):
            high = kline_data[i][2]
            low = kline_data[i][3]
            prev_close = kline_data[i - 1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)

        # 使用 Wilder's Smoothing (RMA) 增量计算所有 ATR 值
        # atr_for_kline[i] 表示截止到 kline_data[i] 的 ATR 值
        atr_for_kline = {}
        atr = sum(tr_list[:atr_period]) / atr_period
        atr_for_kline[atr_period] = atr
        for j in range(atr_period, len(tr_list)):
            atr = (atr * (atr_period - 1) + tr_list[j]) / atr_period
            atr_for_kline[j + 1] = atr

        for i in range(atr_period, len(kline_data)):
            kline = kline_data[i]
            close = kline[4]

            # 使用预计算的 ATR 值
            atr = atr_for_kline[i]
            hl2 = (kline[2] + kline[3]) / 2  # (high + low) / 2

            # 计算基础上下轨
            basic_upper = hl2 + factor * atr
            basic_lower = hl2 - factor * atr

            # 初始化第一次迭代的方向
            if len(directions) == 0:
                if close > basic_upper:
                    direction = -1  # 上升趋势
                    supertrend = basic_lower
                else:
                    direction = 1  # 下降趋势
                    supertrend = basic_upper
            else:
                prev_direction = directions[-1]
                prev_supertrend = supertrend_values[-1]

                # Supertrend 核心逻辑
                if prev_direction == -1:  # 之前是上升趋势
                    # 上升趋势中使用下轨，下轨只能上移或持平
                    final_lower = max(basic_lower, prev_supertrend)

                    if close <= final_lower:
                        # 收盘价跌破下轨，趋势反转为下降
                        direction = 1
                        supertrend = basic_upper
                    else:
                        # 继续上升趋势
                        direction = -1
                        supertrend = final_lower
                else:  # 之前是下降趋势 (direction == 1)
                    # 下降趋势中使用上轨，上轨只能下移或持平
                    final_upper = min(basic_upper, prev_supertrend)

                    if close >= final_upper:
                        # 收盘价突破上轨，趋势反转为上升
                        direction = -1
                        supertrend = basic_lower
                    else:
                        # 继续下降趋势
                        direction = 1
                        supertrend = final_upper

            supertrend_values.append(supertrend)
            directions.append(direction)

        return supertrend_values, directions

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

        return atr

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
                    position_side = PositionSide.Supertrend
                    order_side = OrderSide.BUY if is_long else OrderSide.SELL
                    # 转换为 Observation 对象并保存
                    open_info = Observation(
                        price=current_price,
                        timestamp=current_timestamp,
                        side=order_side,
                        strategy=[position_side],
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

                # 止损触发条件
                sl_triggered = (is_long and current_price <= close_info.stop_loss) or (
                    not is_long and current_price >= close_info.stop_loss
                )
                # 止盈触发条件
                tp_triggered = (
                    is_long and current_price >= close_info.take_profit
                ) or (not is_long and current_price <= close_info.take_profit)

                if sl_triggered:  # 触及止损 - 全仓平仓
                    await self.close_bn_position(
                        symbol, close_info, atr_value, current_price, 1
                    )
                elif tp_triggered:  # 触及止盈 - 部分平仓
                    # 止盈次数+1，加速后续衰减
                    close_info.tp_count += 1
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

                    if close_info.position_side.value == PositionSide.LONG.value:
                        if current_price < close_info.entry_price - atr_value:
                            if PositionSide.Grid not in close_info.strategy:
                                close_info.strategy.append(PositionSide.Grid)
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
                        else:
                            # 做多: 基于入场价格计算初始距离，线性衰减
                            # 衰减系数 = 1 + tp_count (每次止盈后加速)
                            decay_multiplier = 1 + close_info.tp_count
                            initial_tp_gap = (
                                close_info.take_profit
                                - close_info.entry_price
                                - atr_value
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
                                close_info.stop_loss = close_info.entry_price
                            else:
                                # 检测是否达到预期收益的1/3，如果是则设置止损为保护70%盈利
                                profit = current_price - close_info.entry_price
                                target_profit = (
                                    initial_tp_gap / self.TARGET_PROFIT_DIVISOR
                                )  # 预期收益的1/3
                                if profit >= target_profit:
                                    # 达到目标盈利，止损设置为当前盈利回撤30%的位置
                                    # 止损 = 入场价 + 盈利 * TRAILING_STOP_PROFIT_RATIO
                                    trailing_stop = (
                                        close_info.entry_price
                                        + profit * self.TRAILING_STOP_PROFIT_RATIO
                                    )
                                    close_info.stop_loss = max(
                                        close_info.stop_loss,
                                        trailing_stop,
                                    )
                                else:
                                    # 止损上移: 使用当前下轨作为参考，止损只能上移（保护利润）
                                    # 取当前下轨和原止损的较大值
                                    close_info.stop_loss = max(
                                        close_info.stop_loss,
                                        current_lower,
                                    )

                    elif close_info.position_side.value == PositionSide.SHORT.value:
                        if current_price > close_info.entry_price + atr_value:
                            if PositionSide.Grid not in close_info.strategy:
                                close_info.strategy.append(PositionSide.Grid)
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
                        else:
                            # 做空: 止损在上界(stop_loss变量),止盈在下界(take_profit变量)
                            # 衰减系数 = 1 + tp_count (每次止盈后加速)
                            decay_multiplier = 1 + close_info.tp_count
                            initial_tp_gap = (
                                close_info.entry_price
                                - atr_value
                                - close_info.take_profit
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
                                close_info.stop_loss = close_info.entry_price
                            else:
                                # 检测是否达到预期收益的1/3，如果是则设置止损为保护70%盈利
                                profit = close_info.entry_price - current_price
                                target_profit = (
                                    initial_tp_gap / self.TARGET_PROFIT_DIVISOR
                                )  # 预期收益的1/3
                                if profit >= target_profit:
                                    # 达到目标盈利，止损设置为当前盈利回撤30%的位置
                                    # 止损 = 入场价 - 盈利 * TRAILING_STOP_PROFIT_RATIO
                                    trailing_stop = (
                                        close_info.entry_price
                                        - profit * self.TRAILING_STOP_PROFIT_RATIO
                                    )
                                    close_info.stop_loss = min(
                                        close_info.stop_loss,
                                        trailing_stop,
                                    )
                                else:
                                    # 止损下移: 使用当前上轨作为参考，止损只能下移（保护利润）
                                    # 取当前上轨和原止损的较小值
                                    close_info.stop_loss = min(
                                        close_info.stop_loss,
                                        current_upper,
                                    )

                    # 更新回字典
                    self.alert_all["POSITIONS"][symbol] = close_info.model_dump()
            elif open_info:
                # 检查UTC0日期：如果当前时间和open_info不是同一天(UTC0)则跳过
                open_info_date_utc = datetime.datetime.fromtimestamp(
                    open_info.timestamp, datetime.UTC
                ).date()
                current_date_utc = datetime.datetime.now(datetime.UTC).date()
                if (
                    PositionSide.Supertrend not in open_info.strategy
                    and open_info_date_utc != current_date_utc
                    or PositionSide.Supertrend in open_info.strategy
                    and current_timestamp - open_info.timestamp
                    > self.OBSERVATION_TIMEOUT_SECONDS
                ):
                    self.alert_all["OBSERVATIONS"].pop(symbol)
                    self.alert_all["OBSERVATIONS"][symbol] = open_info.model_dump()
                else:
                    should_open = False
                    if (
                        PositionSide.BZ in open_info.strategy
                        and PositionSide.Supertrend not in open_info.strategy
                        and kline_close[-2] < current_price
                        and await self.check_side(
                            semaphore,
                            symbol,
                            PositionSide.LONG.value,
                            kline_close,
                            kline_volume,
                            dtn,
                        )
                        and await self.check_oi(semaphore, symbol, open_info, dtn)
                    ):
                        open_info.side = OrderSide.BUY
                        should_open = True
                    elif (
                        PositionSide.BD in open_info.strategy
                        and PositionSide.Supertrend not in open_info.strategy
                        and current_price < kline_close[-2]
                        and await self.check_oi(semaphore, symbol, open_info, dtn)
                    ):
                        open_info.side = OrderSide.SELL
                        should_open = True
                    elif (lsr_cache := self._long_short_ratio_cache.get(symbol)) and (
                        basis_rate := await self.get_basis_rate(symbol)
                    ) != 0:
                        lsr_value = float(lsr_cache["data"][-1]["longShortRatio"])
                        # BZ下做多：基差率 < -2% 且多空比 < 4/6
                        if (
                            PositionSide.BZ in open_info.strategy
                            and basis_rate < -self.BASIS_RATE_THRESHOLD
                            and lsr_value < self.LONG_SHORT_RATIO_BZ_MAX
                        ):
                            open_info.side = OrderSide.BUY
                            should_open = True
                        # BD下做空：基差率 > 2% 且多空比 > 6/4
                        elif (
                            PositionSide.BD in open_info.strategy
                            and basis_rate > self.BASIS_RATE_THRESHOLD
                            and lsr_value > 1 / self.LONG_SHORT_RATIO_BZ_MAX
                        ):
                            open_info.side = OrderSide.SELL
                            should_open = True
                    if should_open:
                        # 使用15分钟K线的ATR计算止盈止损（与supertrend保持一致）
                        atr_value = self.calculate_atr(kline)
                        is_long = open_info.side.value == OrderSide.BUY.value
                        # 使用hl2中间价计算止盈止损，与supertrend上下轨计算方式一致
                        hl2 = (kline[-1][2] + kline[-1][3]) / 2  # (high + low) / 2
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
                        )
                        self.alert_all["POSITIONS"][symbol] = close_info.model_dump()
                        # 更新timestamp为当前时间，确保同一天(UTC)内不会再次触发Supertrend开仓
                        open_info.timestamp = current_timestamp
                        if PositionSide.Supertrend not in open_info.strategy:
                            open_info.strategy.append(PositionSide.Supertrend)
                        self.alert_all["OBSERVATIONS"][symbol] = open_info.model_dump()

            else:
                # 做多信号判断
                if kline_close[-2] < current_price and kline_volume[-1] == max(
                    kline_volume[-self.VOLUME_LOOKBACK_PERIOD :]
                ):
                    is_long = True
                    open_info = Observation(
                        price=current_price,
                        timestamp=current_timestamp,
                        side=OrderSide.BUY,
                        strategy=[PositionSide.BZ],
                        name=symbol,
                    )

                # 做空信号判断
                elif await self.check_side(
                    semaphore,
                    symbol,
                    PositionSide.SHORT.value,
                    kline_close,
                    kline_volume,
                    dtn,
                ):
                    is_long = False
                    open_info = Observation(
                        price=current_price,
                        timestamp=current_timestamp,
                        side=OrderSide.SELL,
                        strategy=[PositionSide.BD],
                        name=symbol,
                    )
                if open_info:
                    atr_value = self.calculate_atr(kline)
                    zy, zs = self.calc_stop_profit_loss(
                        (kline[-1][2] + kline[-1][3]) / 2,
                        is_long=is_long,
                        atr=atr_value,
                    )
                    if zy == 0 and zs == 0:
                        return
                    rate_show = atr_value * self.SUPERTREND_FACTOR / current_price
                    self.send_msg(
                        f"==={symbol}**{','.join([ps.value for ps in open_info.strategy])}**===\n价格:{current_price}\n止盈:{zy}\n止损:{zs}\n收益率:{rate_show:.2%}"
                    )
                    self.alert_all["OBSERVATIONS"][symbol] = open_info.model_dump()
        except Exception:
            self.logger.exception("处理持仓信息时发生异常")
            return

    def get_symbols_info(self):
        # 获取交易所信息
        exchange_info = self.um_futures_client.exchange_info()

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

    def get_position_risk(self):
        # 获取当前持仓信息，用于清理无效持仓
        position_risk = self.um_futures_client.get_position_risk()
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
            # 获取策略信息
            strategy_tag = ""
            if p["symbol"] in self.alert_all["POSITIONS"]:
                pos_data = self.alert_all["POSITIONS"][p["symbol"]]
                if isinstance(pos_data, dict) and "strategy" in pos_data:
                    strategy_list = pos_data["strategy"]
                    strategy_tag = ",".join(strategy_list) if strategy_list else ""
            positions_data.append(
                f"==={p['symbol']}===\n策略:{strategy_tag}\n开仓价格:{entryPrice} USDT\n持仓方向:{p['positionSide']}\n名义价值:{p['notional']} USDT\n持仓盈亏:{p['unRealizedProfit']} USDT\n持仓收益:{float(p['unRealizedProfit']) / abs(float(p['notional'])):.2%}"
            )

            if p["symbol"] not in self.alert_all["POSITIONS"]:
                # 发现未记录的持仓,止盈止损暂设为0,等待rzq_token用ATR更新
                if p["positionSide"] == PositionSide.LONG.value:
                    close_info = Position(
                        take_profit=0,  # 标记:需要ATR更新
                        stop_loss=0,  # 标记:需要ATR更新
                        close_side=OrderSide.SELL,
                        position_side=PositionSide.LONG,
                        entry_price=entryPrice,
                        name=p["symbol"],
                        date=int(datetime.datetime.now().strftime("%Y%m%d")),
                        strategy=[PositionSide.DK],
                    )
                    self.alert_all["POSITIONS"][p["symbol"]] = close_info.model_dump()
                else:
                    close_info = Position(
                        take_profit=0,  # 标记:需要ATR更新
                        stop_loss=0,  # 标记:需要ATR更新
                        close_side=OrderSide.BUY,
                        position_side=PositionSide.SHORT,
                        entry_price=entryPrice,
                        name=p["symbol"],
                        date=int(datetime.datetime.now().strftime("%Y%m%d")),
                        strategy=[PositionSide.DK],
                    )
                    self.alert_all["POSITIONS"][p["symbol"]] = close_info.model_dump()
            else:
                # 更新现有持仓的开仓价格
                # 先转换为对象，更新属性，再转换回列表
                current_pos_list = self.alert_all["POSITIONS"][p["symbol"]]
                # 兼容旧数据：如果列表长度小于5，说明缺少entry_price，from_list会自动处理
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
            error_msg = f"{market} 市场分析任务超时(5分钟)，已强制中断"
            self.logger.error(error_msg)
            self.send_msg(error_msg)
        except Exception as e:
            error_msg = f"{market} 市场分析任务异常: {str(e)}"
            self.logger.error(error_msg)
            self.logger.exception("市场分析任务发生异常")
            self.send_msg(error_msg)

    async def _rzq_market_impl(self, market):
        """市场分析的实际实现"""
        now = datetime.datetime.now()
        self.is_early_morning = now.hour == self.EARLY_MORNING_HOUR and now.minute == 0

        # 重试机制：最多尝试10次获取交易对信息
        if now.minute % 15 == 0 or not self.symbols:
            for i in range(self.MAX_RETRY_COUNT):
                try:
                    positions_data = self.get_position_risk()
                    self.get_symbols_info()
                    self.symbols = list(self.symbols_info.keys())
                    break  # 成功获取，退出重试循环
                except Exception:
                    # 获取失败，等待后重试
                    self.logger.exception("获取交易对信息时发生异常")
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)
        if self.is_early_morning:
            balance = self.um_futures_client.account()["totalWalletBalance"]
            self.send_msg(f"账户余额:\n{balance} USDT\n持仓信息:\n{positions_data}")
            self.logger.info("账户信息推送任务执行完成")
            with open(self.alert_all_file, "w") as f:
                json.dump(self.alert_all, f, ensure_ascii=False, indent=4)
        # 创建信号量，限制最大并发数，避免API限制
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
        self.logger.info(f"{market}任务开始 - 总交易对数量: {len(self.symbols)}")

        success = set()  # 记录成功处理的交易对

        # 优化：移除 chunk 分批逻辑，改用全量任务提交 + Semaphore 控制并发
        # 这样可以避免"最慢任务拖慢整批进度"的问题，大幅提高整体吞吐量
        tasks = [
            self.rzq_token(semaphore, symbol, success, now) for symbol in self.symbols
        ]

        # 等待所有任务完成
        if tasks:
            await asyncio.gather(*tasks)

        # 打印任务完成信息
        self.logger.info(f"{market}任务结束 - 总交易对数量: {len(success)}")


class AUTOA:
    # ==================== ATR风控常量 ====================
    ATR_PERIOD = 10  # ATR计算周期

    # ==================== 切比雪夫概率阈值常量 ====================
    CHEBYSHEV_EXTREME_THRESHOLD = 0.05  # 极端异常阈值（5%），用于检测非常罕见的事件

    # ==================== 时间常量 ====================
    OBSERVATION_TIMEOUT_SECONDS = 20 * 24 * 60 * 60  # 观察记录超时时间（20天）

    # ==================== Supertrend Constants ====================
    SUPERTREND_FACTOR = 3.0

    # ==================== Trading Configuration ====================
    TRADING_DAYS_LOOKBACK = 60
    STOP_LOSS_DECAY = 0.001  # 止损衰减系数 (1‰)
    TRAILING_STOP_PROFIT_RATIO = 0.7  # 追踪止损盈利保护比例 (保护70%盈利，允许30%回撤)
    MARKET_CLOSE_HOUR = 15  # A股收盘小时
    MARKET_CLOSE_MINUTE = 5  # A股收盘分钟
    MONITOR_TIMEOUT = 600  # 股票监控超时时间（秒）

    # ==================== 均线与筛选常量 ====================
    MA_PERIOD = 10  # 均线周期
    BREAK_MA_LOOKBACK_DAYS = 5  # 跌破均线检查天数
    DEFAULT_POSITION_SHARES = 100  # 假设持仓股数（用于盈亏计算）
    VOLUME_LOOKBACK_MULTIPLIER = 2  # 成交量回溯倍数
    ZT_BOARD_COUNT = 1  # 筛选连板数（1=首板）
    VOLUME_LOOKBACK_PERIOD = 10  # 成交量检查回溯周期
    TARGET_PROFIT_DIVISOR = 3.0  # 目标收益分割系数（用于计算1/3收益触发点）

    qy_key = "6f2ec864-c474-4c8f-b069-1e3c35eb7d73"
    alert_all_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "alert_all_A.json"
    )
    alert_all = json.load(open(alert_all_file, "r", encoding="utf-8"))
    zt_dates = []
    hist_cache = {}
    # 添加线程锁以保护 baostock 查询操作(baostock 不是线程安全的)
    _bs_lock = threading.Lock()
    logger = logging.getLogger("AUTOA")
    logger.propagate = False  # 防止日志向上层传播导致重复

    # 退出处理函数,在脚本退出时保存A股数据
    @staticmethod
    def _save_alert_all_on_exit():
        """脚本退出时保存AUTOA的alert_all数据到文件"""
        try:
            AUTOA.logger.info(f"脚本退出,正在保存A股数据到 {AUTOA.alert_all_file}...")
            with open(AUTOA.alert_all_file, "w", encoding="utf-8") as f:
                json.dump(AUTOA.alert_all, f, ensure_ascii=False, indent=4)
            AUTOA.logger.info("A股数据保存完成")
        except Exception as e:
            AUTOA.logger.error(f"保存A股数据失败: {str(e)}")
            AUTOA.logger.exception("保存A股数据时发生异常")

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
        return sum(tr_list[-period:]) / min(len(tr_list), period)

    @classmethod
    def calculate_trend(cls, hist_data: pd.DataFrame, factor=None, atr_period=None):
        """
        计算 Supertrend 指标 (A股适配版)

        参数:
            hist_data: K线数据 DataFrame
            factor: 因子，默认使用类常量 SUPERTREND_FACTOR
            atr_period: ATR周期，默认使用类常量 ATR_PERIOD

        返回:
            (supertrend_values, directions, atr_values, upper_values, lower_values):
            supertrend值列表、方向列表、ATR值列表、上轨值列表、下轨值列表
            方向: -1 表示上升趋势, 1 表示下降趋势
        """
        if factor is None:
            factor = cls.SUPERTREND_FACTOR
        if atr_period is None:
            atr_period = cls.ATR_PERIOD
        if hist_data.empty or len(hist_data) < atr_period + 1:
            return [], [], [], [], []

        supertrend_values = []
        directions = []
        atr_values = []
        upper_values = []  # 上轨值列表
        lower_values = []  # 下轨值列表

        # 缓存列数据加速访问
        highs = hist_data["high"].values
        lows = hist_data["low"].values
        closes = hist_data["close"].values

        # 预计算所有 TR 值
        tr_list = []
        for i in range(1, len(hist_data)):
            h = float(highs[i])
            low_price = float(lows[i])
            pc = float(closes[i - 1])
            tr = max(h - low_price, abs(h - pc), abs(low_price - pc))
            tr_list.append(tr)

        if not tr_list or len(tr_list) < atr_period:
            return [], [], [], [], []

        # 使用 Wilder's Smoothing (RMA) 增量计算所有 ATR 值
        # atr_for_index[i] 表示截止到 hist_data[i] 的 ATR 值
        atr_for_index = {}
        atr = sum(tr_list[:atr_period]) / atr_period
        atr_for_index[atr_period] = atr
        for j in range(atr_period, len(tr_list)):
            atr = (atr * (atr_period - 1) + tr_list[j]) / atr_period
            atr_for_index[j + 1] = atr

        for i in range(atr_period, len(hist_data)):
            # 使用预计算的 ATR 值
            atr = atr_for_index[i]
            atr_values.append(atr)

            # 当前K线数据
            current_high = float(highs[i])
            current_low = float(lows[i])
            current_close = float(closes[i])

            hl2 = (current_high + current_low) / 2

            # 计算基础上下轨
            basic_upper = hl2 + factor * atr
            basic_lower = hl2 - factor * atr
            upper_values.append(basic_upper)  # 保存当前上轨
            lower_values.append(basic_lower)  # 保存当前下轨

            if len(directions) == 0:
                if current_close > basic_upper:
                    direction = -1  # 上升
                    supertrend = basic_lower
                else:
                    direction = 1  # 下降
                    supertrend = basic_upper
            else:
                prev_direction = directions[-1]
                prev_supertrend = supertrend_values[-1]

                if prev_direction == -1:  # 之前是上升趋势
                    final_lower = max(basic_lower, prev_supertrend)
                    if current_close <= final_lower:
                        direction = 1  # 反转为下降
                        supertrend = basic_upper
                    else:
                        direction = -1  # 继续上升
                        supertrend = final_lower
                else:  # 之前是下降趋势
                    final_upper = min(basic_upper, prev_supertrend)
                    if current_close >= final_upper:
                        direction = -1  # 反转为上升
                        supertrend = basic_lower
                    else:
                        direction = 1  # 继续下降
                        supertrend = final_upper

            supertrend_values.append(supertrend)
            directions.append(direction)

        return supertrend_values, directions, atr_values, upper_values, lower_values

    @classmethod
    async def check_trend(cls, code, zt_dates=None, kline_data=None, check_at_index=-1):
        """
        检查趋势信号 - 基于 Supertrend 指标 (A股适配版)

        功能: 使用 Supertrend 指标判断市场趋势方向
        参数:
            code: 股票代码
            zt_dates: 交易日期列表
            kline_data: K线数据(可选,如果不提供则获取)
            check_at_index: 检查信号的索引位置，默认-1（最后一个点与前一个点比较）
        返回:
            (signal, last_atr, supertrend_values): 信号('LONG'/'SHORT'/0)、最后一个点的ATR值 和 supertrend值列表
        """
        try:
            atr_period = cls.ATR_PERIOD
            factor = cls.SUPERTREND_FACTOR

            # 如果未提供K线数据，则获取
            if kline_data is None:
                if zt_dates is None:
                    zt_dates = cls.get_last_trading_days(days=cls.TRADING_DAYS_LOOKBACK)

                if not zt_dates:
                    return 0, 0.0

                kline_data = await cls.stock_zh_a_hist(
                    code,
                    "date,code,open,high,low,close,preclose,volume,amount",
                    start_date=zt_dates[-1],
                    end_date=zt_dates[0],
                )

            if kline_data.empty or len(kline_data) < atr_period + 1:
                return 0, 0.0, [], 0.0, 0.0

            supertrend_values, directions, atr_values, upper_values, lower_values = (
                cls.calculate_trend(kline_data, factor=factor, atr_period=atr_period)
            )

            last_atr = atr_values[-1] if atr_values else 0.0
            current_upper = upper_values[-1] if upper_values else 0.0
            current_lower = lower_values[-1] if lower_values else 0.0

            if len(directions) < 2:
                return 0, last_atr, supertrend_values, current_upper, current_lower

            # 转换为实际索引
            idx = (
                check_at_index
                if check_at_index >= 0
                else len(directions) + check_at_index
            )
            if idx < 1 or idx >= len(directions):
                return 0, last_atr, supertrend_values, current_upper, current_lower

            prev_direction = directions[idx - 1]
            curr_direction = directions[idx]

            # 检测趋势变化
            if prev_direction == 1 and curr_direction == -1:
                return (
                    PositionSide.LONG.value,
                    last_atr,
                    supertrend_values,
                    current_upper,
                    current_lower,
                )  # 做多信号
            elif prev_direction == -1 and curr_direction == 1:
                return (
                    PositionSide.SHORT.value,
                    last_atr,
                    supertrend_values,
                    current_upper,
                    current_lower,
                )  # 做空信号
            else:
                return 0, last_atr, supertrend_values, current_upper, current_lower

        except Exception:
            cls.logger.exception(f"检查 {code} 趋势信号时发生错误")
            return 0, 0.0, []

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
        yesterday_below_ma10 = (
            pd.notna(ma10.iloc[-2])
            and float(hist.iloc[-2]["close"]) < float(ma10.iloc[-2])
        )
        day_before_below_ma10 = (
            pd.notna(ma10.iloc[-3])
            and float(hist.iloc[-3]["close"]) < float(ma10.iloc[-3])
        )

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
    def send_msg(cls, msg):
        """
        发送消息通知函数

        功能：通过企业微信发送交易通知消息
        参数：
            msg: 要发送的消息内容
        """
        try:
            # 记录发送时间，便于调试和追踪
            cls.logger.info(f"发送消息: {msg}")
            # 企业微信发送格式：使用企业微信机器人webhook
            json_msg = {"msgtype": "text", "text": {"content": msg}}
            response = session.post(
                url=f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={cls.qy_key}",
                json=json_msg,
            )

            # 检查发送结果，失败时记录状态码
            if response.status_code != 200:
                cls.logger.error(f"消息发送失败，状态码: {response.status_code}")
        except Exception as e:
            # 异常处理：记录错误但不中断程序运行
            cls.logger.error(f"消息发送异常: {str(e)}")

    @staticmethod
    def get_last_trading_days(today=None, days=None):
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
            trade_dates = ak.tool_trade_date_hist_sina()
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
            loop = asyncio.get_running_loop()
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

                data_list = await loop.run_in_executor(
                    None,
                    fetch_bs_data,
                    code_pre,
                    code,
                    fields,
                    start_date,
                    end_date,
                    frequency,
                    adjustflag,
                    cls._bs_lock,
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

            def fetch_sina_data(stock_code_pre, stock_code):
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://finance.sina.com.cn/",
                }
                dl = []
                try:
                    dl = requests.get(
                        url=f"https://cn.finance.sina.com.cn/minline/getMinlineData?symbol={stock_code_pre}{stock_code}",
                        headers=headers,
                    ).json()["result"]["data"]
                except Exception:
                    pass
                return dl

            res = await loop.run_in_executor(None, fetch_sina_data, code_pre, code)
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
        if price_close <= close_info.stop_loss or price_close >= close_info.take_profit:
            # 从持仓列表移除
            cls.alert_all["POSITIONS"].pop(code)

            # 发送平仓通知
            entry_price = (
                close_info.entry_price if close_info.entry_price > 0 else price_close
            )
            profit_rate = (price_close / entry_price - 1) if entry_price > 0 else 0
            realized_pnl = (price_close - entry_price) * cls.DEFAULT_POSITION_SHARES
            strategy_tag = ",".join([ps.value for ps in close_info.strategy])
            msg = f"{close_info.name} 平仓\n策略:{strategy_tag}\n委托价格:{price_close:.2f}\n平仓收益:{profit_rate:.2%}"
            cls.send_msg(msg)

            # 记录平仓到Excel
            CloseRecordManager.record_close(
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
            )
        else:
            # 未触及止盈止损，执行移动止损逻辑
            supertrend_values, directions, atr_values, upper_values, lower_values = (
                cls.calculate_trend(
                    hist, factor=cls.SUPERTREND_FACTOR, atr_period=cls.ATR_PERIOD
                )
            )

            # 参照 AUTOBN 的动态止盈止损逻辑
            DECAY = cls.STOP_LOSS_DECAY

            # 使用 calculate_trend 返回的当前上下轨
            current_upper = upper_values[-1] if upper_values else close_info.take_profit
            current_lower = lower_values[-1] if lower_values else close_info.stop_loss

            atr_value = atr_values[-1] if atr_values else 0.0
            if (
                atr_value > 0
                and close_info.entry_price > 0
                and price_close < close_info.entry_price - atr_value
            ):
                if PositionSide.Grid not in close_info.strategy:
                    close_info.strategy.append(PositionSide.Grid)
                strategy_tag = ",".join([ps.value for ps in close_info.strategy])
                msg = (
                    f"{close_info.name} 加仓\n"
                    f"策略:{strategy_tag}\n"
                    f"委托价格:{price_close:.2f}\n"
                    f"止盈:{close_info.take_profit:.2f}\n"
                    f"止损:{close_info.stop_loss:.2f}"
                )
                cls.send_msg(msg)
                close_info.entry_price = (close_info.entry_price + price_close) / 2
            else:
                # 做多: 止盈在上方，止损在下方
                # 止盈下移: 取衰减后的值和当前上轨的较小值
                initial_tp_gap = (
                    close_info.take_profit - close_info.entry_price - atr_value
                )
                tp_decay_step = initial_tp_gap * DECAY
                decayed_tp = close_info.take_profit - tp_decay_step
                close_info.take_profit = min(decayed_tp, current_upper)

                # 检测是否达到预期收益的1/3，如果是则设置止损为保护70%盈利
                profit = price_close - close_info.entry_price
                target_profit = initial_tp_gap / cls.TARGET_PROFIT_DIVISOR  # 预期收益的1/3
                if profit >= target_profit:
                    # 达到目标盈利，止损设置为当前盈利回撤30%的位置
                    # 止损 = 入场价 + 盈利 * TRAILING_STOP_PROFIT_RATIO
                    trailing_stop = (
                        close_info.entry_price + profit * cls.TRAILING_STOP_PROFIT_RATIO
                    )
                    close_info.stop_loss = max(close_info.stop_loss, trailing_stop)
                else:
                    # 止损上移: 使用当前下轨作为参考，止损只能上移（保护利润）
                    # 取当前下轨和原止损的较大值
                    close_info.stop_loss = max(close_info.stop_loss, current_lower)

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
        if len(hist_volume) >= 3:
            should_open = False
            # 先计算 supertrend 和 ATR（两种策略都需要）
            (
                trend_signal,
                current_atr,
                supertrend_values,
                current_upper,
                current_lower,
            ) = await cls.check_trend(code, zt_dates, hist, check_at_index=-1)
            if (
                hist_open[-1] > hist_high[-2]
                and hist_volume[-1] == max(hist_volume[-cls.ATR_PERIOD * cls.VOLUME_LOOKBACK_MULTIPLIER :])
                and cls.calculate_chebyshev_probability(
                    hist_volume[-cls.ATR_PERIOD * cls.VOLUME_LOOKBACK_MULTIPLIER : -cls.ATR_PERIOD],
                    hist_volume[-1],
                )["chebyshev_upper_bound"]
                < cls.CHEBYSHEV_EXTREME_THRESHOLD
            ):
                if PositionSide.BZ not in open_info.strategy:
                    open_info.strategy.append(PositionSide.BZ)
                should_open = True
            elif cls.check_gap_up_after_break_ma10(hist):
                if PositionSide.Supertrend not in open_info.strategy:
                    open_info.strategy.append(PositionSide.Supertrend)
                should_open = True

            if should_open and current_atr > 0:
                price_close = float(hist.iloc[-1]["close"])
                # 止盈使用check_trend返回的当前上轨
                take_profit = current_upper
                stop_loss = supertrend_values[-1]
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
                    f"==={open_info.name}**{','.join(open_info.strategy)}**===\n"
                    f"价格:{price_close:.2f}\n"
                    f"止盈:{take_profit:.2f}\n"
                    f"止损:{stop_loss:.2f}\n"
                    f"收益率:{atr_percent:.2%}\n"
                )
                cls.send_msg(msg)

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
        # 收盘后不执行：小时大于15，或者小时等于15且分钟大于0
        is_after_close = today.hour > cls.MARKET_CLOSE_HOUR or (
            today.hour == cls.MARKET_CLOSE_HOUR
            and today.minute > cls.MARKET_CLOSE_MINUTE
        )
        if (
            cls.zt_dates and today.strftime("%Y-%m-%d") not in cls.zt_dates
        ) or is_after_close:
            return []
        if not cls.zt_dates:
            cls.zt_dates = cls.get_last_trading_days(today)
            if not cls.zt_dates:
                return []
        selected = set()  # 存储符合条件的股票
        if today.hour == cls.MARKET_CLOSE_HOUR:
            with open(cls.alert_all_file, "w", encoding="utf-8") as f:
                json.dump(cls.alert_all, f, ensure_ascii=False, indent=4)
            zt_df = ak.stock_zt_pool_em(date=cls.zt_dates[0].replace("-", ""))
            stock_codes = zt_df[["代码", "名称", "连板数"]].values.tolist()
            for code in stock_codes:
                if (
                    code[2] == cls.ZT_BOARD_COUNT
                    and code[0] not in cls.alert_all["POSITIONS"]
                    and code[0] not in cls.alert_all["OBSERVATIONS"]
                ):
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

        # 创建异步任务列表，并发处理持仓和观察列表
        tasks = [
            cls.on_positions(code, cls.zt_dates, close_info, today)
            for code, close_info in cls.alert_all["POSITIONS"].items()
        ] + [
            cls.on_observations(code, cls.zt_dates, open_info, today)
            for code, open_info in cls.alert_all["OBSERVATIONS"].items()
            if code not in cls.alert_all["POSITIONS"]
        ]
        # 等待所有任务完成
        await asyncio.gather(*tasks)
        gc.collect()  # 垃圾回收，释放内存
        return selected

    @classmethod
    async def monitor_stocks(cls):
        """
        监控A股并发送通知

        功能：筛选符合条件的A股股票，并通过企业微信发送通知
        策略：低吸策略，寻找回调买入机会
        """
        try:
            # 设置超时时间为10分钟，防止任务卡住
            cls.logger.info("A股监控任务开始")
            await asyncio.wait_for(
                cls._monitor_stocks_impl(), timeout=cls.MONITOR_TIMEOUT
            )
        except asyncio.TimeoutError:
            error_msg = "A股监控任务超时(10分钟)，已强制中断"
            cls.logger.error(error_msg)
            cls.send_msg(error_msg)
        except Exception as e:
            error_msg = f"A股监控任务异常: {str(e)}"
            cls.logger.error(error_msg)
            cls.logger.exception("A股监控任务发生异常")
            cls.send_msg(error_msg)

    @classmethod
    async def _monitor_stocks_impl(cls):
        """A股监控的实际实现"""
        # 登录系统（使用异步执行，避免阻塞事件循环）
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, bs.login)
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
                cls.send_msg(content)

        finally:
            # 确保总是登出，即使发生异常（使用异步执行）
            await loop.run_in_executor(None, bs.logout)


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

    autobn = AUTOBN.from_cfg(
        bn_api_file=os.path.join(current_dir, "bn.json"),
        alert_all_file=os.path.join(current_dir, "alert_all.json"),
        qy_key=qy_key,
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
        minute="*/5",  # 每5分钟执行一次
        second="00",  # 整点秒数
        day_of_week="mon-fri",  # 周一至周五（交易日）
        timezone="Asia/Shanghai",  # 上海时区
        misfire_grace_time=60,  # 错过执行的宽限时间（秒）
        max_instances=1,  # 同一时间只允许1个实例运行
        coalesce=False,  # 改为False，避免合并错过的执行导致任务堆积和卡住
        name="股票监控任务",  # 任务名称
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
