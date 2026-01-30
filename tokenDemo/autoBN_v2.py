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
from decimal import Decimal, ROUND_DOWN
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


class Direction(str, Enum):
    """持仓方向枚举"""

    LONG = "LONG"
    SHORT = "SHORT"


class Strategy(str, Enum):
    """交易策略枚举"""

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
    position_side: Direction
    entry_price: float
    name: str
    date: int
    strategy: List[Strategy]
    tp_count: int = 0  # 止盈次数，每次部分止盈后+1，衰减加速系数


class Observation(BaseModel):
    """
    观察列表信息数据类 (AUTOBN/AUTOA 通用)

    用途：记录待观察的交易机会
    字段：
        price: 触发价格
        timestamp: 触发时间（Unix时间戳）
        side: 信号方向 (BUY/SELL)
        strategy: 策略标签列表 (BZ/BD/DK/Supertrend/Grid)
        name: 品种名称 (AUTOBN: symbol, AUTOA: 股票名称)
    """

    price: float
    timestamp: float
    side: OrderSide
    strategy: List[Strategy]
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


# ==================== BaseTrader 基类 ====================


class BaseTrader:
    """
    交易基类 - AUTOBN 和 AUTOA 的共用基类

    提供共用常量、指标计算方法和交易逻辑方法。
    子类需要实现 _to_dataframe 和 send_msg 抽象方法。
    """

    # ==================== 共用常量 ====================
    ATR_PERIOD = 10  # ATR计算周期
    SUPERTREND_FACTOR = 3.0  # ATR倍数，用于计算止盈止损和supertrend上下轨
    CHEBYSHEV_EXTREME_THRESHOLD = 0.05  # 极端异常阈值（5%），用于检测非常罕见的事件
    TRAILING_STOP_PROFIT_RATIO = 0.7  # 追踪止损盈利保护比例 (保护70%盈利，允许30%回撤)
    STOP_LOSS_DECAY_PER_MINUTE = 0.0001  # 每分钟止盈止损衰减比例 (0.01%)
    PARTIAL_CLOSE_RATIO = 0.7  # 部分平仓比例 (止盈时使用)

    # ==================== 抽象方法 ====================

    def _to_dataframe(self, data) -> pd.DataFrame:
        """
        将数据转换为统一的 DataFrame 格式

        子类必须实现此方法，将自身的数据格式转换为包含 'high', 'low', 'close' 列的 DataFrame。

        参数:
            data: 原始数据（AUTOBN: kline列表, AUTOA: DataFrame）

        返回:
            pd.DataFrame: 包含 'high', 'low', 'close' 列的 DataFrame

        注意:
            AUTOBN 子类实现: kline_data[i][2]=high, [3]=low, [4]=close
            AUTOA 子类实现: 直接返回 hist[['high', 'low', 'close']]
        """
        raise NotImplementedError("子类必须实现 _to_dataframe 方法")

    def send_msg(self, msg: str, **kwargs):
        """
        发送通知消息

        子类必须实现此方法，用于发送交易通知、告警等消息。

        参数:
            msg: 消息内容
            **kwargs: 其他参数（如消息类型、优先级等）
        """
        raise NotImplementedError("子类必须实现 send_msg 方法")

    # ==================== 指标计算方法 ====================

    def calculate_atr(self, df: pd.DataFrame, period: Optional[int] = None) -> float:
        """
        计算ATR (平均真实波幅) - 使用 Wilder's Smoothing (RMA)

        参数:
            df: DataFrame, 必须包含 'high', 'low', 'close' 列
            period: ATR周期，默认使用 self.ATR_PERIOD

        返回:
            float: ATR值，数据不足时返回 0.0
        """
        if period is None:
            period = self.ATR_PERIOD

        if df is None or len(df) < period + 1:
            return 0.0

        # 计算 True Range
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        tr_list = []
        for i in range(1, len(df)):
            prev_close = close[i - 1]
            # TR = Max(H-L, |H-PC|, |L-PC|)
            tr = max(
                high[i] - low[i],
                abs(high[i] - prev_close),
                abs(low[i] - prev_close),
            )
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

    def calculate_trend(
        self,
        df: pd.DataFrame,
        factor: Optional[float] = None,
        atr_period: Optional[int] = None,
    ) -> tuple:
        """
        计算 Supertrend 指标

        参数:
            df: DataFrame, 必须包含 'high', 'low', 'close' 列
            factor: 因子，默认使用 self.SUPERTREND_FACTOR
            atr_period: ATR周期，默认使用 self.ATR_PERIOD

        返回:
            tuple: (supertrend_values, directions, atr_values, upper_values, lower_values)
            - supertrend_values: supertrend值列表
            - directions: 方向列表 (-1=上升趋势, 1=下降趋势)
            - atr_values: ATR值列表
            - upper_values: 上轨值列表
            - lower_values: 下轨值列表
        """
        if factor is None:
            factor = self.SUPERTREND_FACTOR
        if atr_period is None:
            atr_period = self.ATR_PERIOD

        if df is None or len(df) < atr_period + 1:
            return [], [], [], [], []

        supertrend_values = []
        directions = []
        atr_values = []
        upper_values = []
        lower_values = []

        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        for i in range(atr_period, len(df)):
            # 计算截止到当前K线的ATR
            atr = self.calculate_atr(df.iloc[: i + 1], period=atr_period)
            hl2 = (high[i] + low[i]) / 2  # (high + low) / 2

            # 计算基础上下轨
            basic_upper = hl2 + factor * atr
            basic_lower = hl2 - factor * atr

            # 初始化第一次迭代的方向
            if len(directions) == 0:
                if close[i] > basic_upper:
                    direction = -1  # 上升趋势
                    supertrend = basic_lower
                else:
                    direction = 1  # 下降趋势
                    supertrend = basic_upper
                final_upper = basic_upper
                final_lower = basic_lower
            else:
                prev_direction = directions[-1]
                prev_supertrend = supertrend_values[-1]

                # Supertrend 核心逻辑
                if prev_direction == -1:  # 之前是上升趋势
                    # 上升趋势中使用下轨，下轨只能上移或持平
                    final_lower = max(basic_lower, prev_supertrend)
                    final_upper = basic_upper

                    if close[i] <= final_lower:
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
                    final_lower = basic_lower

                    if close[i] >= final_upper:
                        # 收盘价突破上轨，趋势反转为上升
                        direction = -1
                        supertrend = basic_lower
                    else:
                        # 继续下降趋势
                        direction = 1
                        supertrend = final_upper

            supertrend_values.append(supertrend)
            directions.append(direction)
            atr_values.append(atr)
            upper_values.append(final_upper)
            lower_values.append(final_lower)

        return supertrend_values, directions, atr_values, upper_values, lower_values

    def calculate_chebyshev_probability(self, data, value: float) -> dict:
        """
        计算给定数值对应的切比雪夫概率

        功能：根据切比雪夫不等式计算给定数值在数据分布中的概率特征

        切比雪夫不等式：P(|X - μ| >= kσ) <= 1/k²
        换言之：至少有 (1 - 1/k²) 的数据落在 [μ - kσ, μ + kσ] 区间内

        参数:
            data: 数据（支持 list、pd.Series、pd.DataFrame 单列）
            value: 给定的数值，用于计算其在分布中的位置

        返回:
            dict: 包含以下信息：
            - mean: 数据均值
            - std: 数据标准差
            - k: 给定数值距离均值的标准差倍数
            - chebyshev_upper_bound: 切比雪夫不等式的上界概率 (1/k²)
            - min_probability_in_range: 至少有该比例的数据在 k 个标准差范围内 (1 - 1/k²)
            - deviation: 给定数值与均值的偏差
        """
        # 统一数据格式
        if isinstance(data, pd.DataFrame):
            if len(data.columns) == 1:
                data_list = data.iloc[:, 0].tolist()
            else:
                raise ValueError("DataFrame 必须只有一列")
        elif isinstance(data, pd.Series):
            data_list = data.tolist()
        elif isinstance(data, list):
            data_list = data
        else:
            raise ValueError(f"不支持的数据类型: {type(data)}")

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

    # ==================== 交易逻辑方法 ====================

    def calc_stop_profit_loss(
        self, price: float, is_long: bool = True, atr: float = 0
    ) -> tuple:
        """
        止盈止损计算辅助函数 (使用 supertrend 的 factor 倍 ATR)

        参数:
            price: 当前价格
            is_long: 是否做多 (True=做多, False=做空)
            atr: ATR值

        返回:
            tuple: (止盈价, 止损价)
            - 做多时: (上界/止盈位, 下界/止损位)
            - 做空时: (下界/止盈位, 上界/止损位)
        """
        if atr <= 0:
            return (0, 0)

        # 使用 supertrend 的 factor 倍 ATR 作为止盈止损距离
        atr_distance = atr * self.SUPERTREND_FACTOR
        if is_long:
            return (price + atr_distance, price - atr_distance)
        else:
            # 做空：返回 (下界/止盈位, 上界/止损位)
            return (price - atr_distance, price + atr_distance)


# ==================== AUTOBN 币安期货 ====================
