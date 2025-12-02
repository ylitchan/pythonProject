# ==================== 标准库导入 ====================
import asyncio
import copy
import datetime
import gc
import json
import os
import time
import traceback
from decimal import Decimal, ROUND_DOWN
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

# ==================== 第三方库导入 ====================
import akshare as ak
import baostock as bs
import pandas as pd
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from binance.um_futures import UMFutures

# ==================== 类型定义 ====================


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BZ1 = "BZ1"
    BZ2 = "BZ2"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Position:
    """
    持仓信息数据类

    数据结构对应：[止盈价, 止损价, 平仓方向, 持仓方向, 开仓均价]
    """

    take_profit: float  # 止盈价 [0]
    stop_loss: float  # 止损价 [1]
    close_side: OrderSide  # 平仓方向 [2] (BUY/SELL)
    position_side: str  # 持仓方向/策略标签 [3] (LONG/SHORT/BZ1/BZ2)
    entry_price: float = 0.0  # 开仓均价 [4]

    def to_list(self) -> List:
        """转换为列表格式（用于JSON存储兼容）"""
        return [
            self.take_profit,
            self.stop_loss,
            self.close_side.value,
            self.position_side,  # 已经是字符串
            self.entry_price,
        ]

    @classmethod
    def from_list(cls, data: List):
        """从列表创建对象"""
        return cls(
            take_profit=float(data[0]),
            stop_loss=float(data[1]),
            close_side=OrderSide(data[2]),
            position_side=data[3],  # 类型注解已声明为str，无需显式转换
            entry_price=float(data[4]) if len(data) > 4 else 0.0,
        )


@dataclass
class Observation:
    """
    观察列表信息数据类

    用途：记录待观察的交易机会
    数据结构对应：[触发价格, 触发时间, 信号方向, 关联信息]
    """

    price: float  # 触发价格 [0]
    timestamp: float  # 触发时间（Unix时间戳）[1]
    side: OrderSide  # 信号方向 [2] (BUY/SELL)
    position_side: (
        str  # [3] 关联信息：持仓方向(LONG/SHORT)、策略标签(BZ1/BZ2)或空字符串
    )

    def to_list(self) -> List:
        """转换为列表格式"""
        return [self.price, self.timestamp, self.side.value, self.position_side]

    @classmethod
    def from_list(cls, data: List):
        """从列表创建对象"""
        return cls(
            price=float(data[0]),
            timestamp=float(data[1]),
            side=OrderSide(data[2]),
            position_side=data[3],  # 类型注解已声明为str，无需显式转换
        )


# HTTP 会话配置（可覆盖）
session = requests.Session()
session.verify = False
session.headers = {"Content-Type": "application/json"}


class AUTOBN:
    """币安期货自动交易类"""

    # ==================== 交易参数常量 ====================
    DEFAULT_CLOSE_RATIO = 0.5  # 默认平仓比例
    DEFAULT_OPEN_RATIO = 0.1  # 默认开仓比例
    MAX_BALANCE_USAGE = 0.7  # 最大资金使用比例
    DEFAULT_LEVERAGE = 1  # 默认杠杆倍数
    MIN_NOTIONAL = 6  # 最小交易额（USDT）

    # ==================== 风控参数常量 ====================
    DEFAULT_HEALTH_THRESHOLD = 70  # 默认健康度阈值
    MAINTENANCE_MARGIN_RATE = 0.004  # 维持保证金率（0.4%）

    # ==================== 并发控制常量 ====================
    MAX_CONCURRENT_REQUESTS = 10  # 最大并发请求数
    CHUNK_SIZE = 10  # 批处理大小

    # ==================== 基差监控常量 ====================
    BASIS_WARNING_THRESHOLD = 1.02  # 基差警告阈值（2%）
    BASIS_ALERT_THRESHOLD = 1.015  # 基差异常阈值（1.5%）
    BASIS_WARNING_COOLDOWN = 60  # 基差警告冷却时间（秒）
    BASIS_ALERT_COOLDOWN = 180  # 基差异常冷却时间（秒）

    # ==================== 时间常量 ====================
    ONE_DAY_SECONDS = 24 * 60 * 60  # 一天的秒数
    TEN_DAY_SECONDS = 10 * 24 * 60 * 60  # 十天的秒数
    FIFTEEN_MIN_SECONDS = 15 * 60  # 15分钟的秒数
    RETRY_DELAY_SECONDS = 2  # 重试延迟（秒）
    CLOSE_RETRY_DELAY = 3  # 平仓重试延迟（秒）

    # ==================== K线相关常量 ====================
    KLINE_LIMIT = 30  # K线数据条数
    MIN_KLINE_FOR_ANALYSIS = 4  # 分析所需最小K线数量

    # ==================== ATR风控常量 ====================
    ATR_PERIOD = 10  # ATR计算周期
    ATR_STOP_LOSS_MULTIPLIER = 0.5  # ATR止损倍数
    ATR_TAKE_PROFIT_MULTIPLIER = 1.0  # ATR止盈倍数 (盈亏比1:2)
    ATR_TRAILING_STOP_MULTIPLIER = 0.5  # ATR移动止损倍数

    # ==================== 切比雪夫概率阈值常量 ====================
    CHEBYSHEV_EXTREME_THRESHOLD = 0.01  # 极端异常阈值（1%），用于检测非常罕见的事件
    CHEBYSHEV_SIGNIFICANT_THRESHOLD = 0.25  # 显著异常阈值（25%），用于检测显著的异常

    @classmethod
    def from_cfg(cls, **kwargs):
        obj = cls.__new__(cls)
        obj.symbols = []
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
        obj.alert_all_old = copy.deepcopy(obj.alert_all)

        # 初始化资金槽位（用于资金管理）（可覆盖）
        # 含义：用于控制单次下单的资金使用上限（与 open_ratio 一起作用）
        obj.slot_balance = kwargs.get("slot_balance", [0.0])
        obj.symbols_info = {}
        obj.is_early_morning = False
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
            # 记录发送时间，便于调试和追踪
            current_time = datetime.datetime.now()
            print(f"{current_time} - 发送消息: {msg}", flush=True)

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
                print(f"消息发送失败，状态码: {response.status_code}", flush=True)
        except Exception as e:
            # 异常处理：记录错误但不中断程序运行
            print(f"消息发送异常: {str(e)}", flush=True)

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

    def get_amount_close(self, symbol):
        """
        获取指定交易对的持仓数量

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
            position = {
                k["symbol"]: abs(float(k["positionAmt"]))
                for k in self.um_futures_client.get_position_risk()
            }
            return position.get(symbol, 0)  # 返回指定交易对的持仓数量
        except Exception:
            # 异常时返回0，避免程序崩溃
            return 0

    def open_bn_position(self, symbol, side, positionSide, open_ratio=0.1):
        """
        在币安期货市场开仓

        功能：执行开仓操作，包含完整的风险控制和资金管理
        参数：
            symbol: 交易对符号，如'BTCUSDT'
            symbols_info: 交易对配置信息（精度等）
            side: 交易方向，'BUY'或'SELL'
            positionSide: 持仓方向，'LONG'或'SHORT'
        返回：
            成功返回symbol，失败返回None
        """
        try:
            # 获取账户可用余额
            account_data = self.um_futures_client.account()
            balance = float(account_data["availableBalance"])
            # 风险控制2：检查可用余额
            if balance <= 0:
                self.send_msg(f"{symbol} 开仓失败：可用余额为零")
                return None

            # 获取当前标记价格（用于计算开仓数量）
            mark_price_data = self.um_futures_client.mark_price(symbol)
            if not mark_price_data:
                self.send_msg(f"{symbol} 开仓失败：无法获取标记价格")
                return None

            markPrice = float(mark_price_data["markPrice"])

            # 风险控制3：检查交易对配置是否存在
            if symbol not in self.symbols_info:
                self.send_msg(f"{symbol} 开仓失败：找不到交易对信息")
                return None

            # 资金管理策略：限制单次开仓金额，控制风险
            # 策略1：设置资金槽位，单次开仓不超过总资金的 open_ratio（默认 1/3）
            self.slot_balance[0] = max(balance * open_ratio, self.slot_balance[0])
            # 策略2：实际开仓金额不超过槽位和总资金的较小值
            safe_balance = min(self.slot_balance[0], balance * self.MAX_BALANCE_USAGE)

            # 计算开仓数量：可用资金 * 杠杆 / 当前价格
            amount_raw = safe_balance * self.leverage / markPrice

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
                self.send_msg(
                    f"{symbol} 开仓失败：交易额 {notional} 低于最小要求 {self.MIN_NOTIONAL} USDT"
                )
                return None

            # 风险控制：检查“账户级健康度”（逐仓建议额外结合仓位强平距离/保证金冗余）
            # 健康度 = (1 - 维持保证金/总余额) * 100%
            # 目的：确保开仓后不会导致全局账户风险过高
            account_health = self.calculate_health_bn(notional)
            if account_health < self.health4open:
                self.send_msg(
                    f"{symbol} 开仓失败：预计健康度 {account_health}% 低于要求 {self.health4open}%"
                )
                return None

            # 设置保证金模式（全仓/逐仓）。若已为目标模式，交易所可能返回错误码或提示，忽略即可
            # try:
            #     self.um_futures_client.change_margin_type(
            #         symbol=symbol, marginType=self.margin_mode)
            # except Exception:
            #     pass

            # 设置杠杆倍数
            leverage_result = self.um_futures_client.change_leverage(
                symbol=symbol, leverage=self.leverage
            )
            actual_leverage = leverage_result.get("leverage", self.leverage)
            # 执行市价单开仓
            tx = self.um_futures_client.new_order(
                symbol=symbol,
                side=side,  # 'BUY'或'SELL'
                type="MARKET",  # 市价单，立即成交
                quantity=amount,  # 开仓数量
                positionSide=positionSide,  # 'LONG'或'SHORT'
            )
            # 发送成功通知
            # 提示：逐仓模式下本次下单会并入同一方向同一 symbol 的逐仓仓位，逐仓保证金与强平价随之重算
            msg = f"{symbol}开仓\n持仓方向:{positionSide}\n杠杆:{actual_leverage}x\n委托数量:{tx.get('origQty', 0)}\n委托价格:{markPrice}\n名义价值:{notional} USDT"
            self.send_msg(msg)
            return account_data
        except Exception as e:
            # 异常处理：记录错误并发送通知
            error_msg = f"{symbol} 开仓失败：{str(e)}"
            self.send_msg(error_msg)
            traceback.print_exc()  # 打印详细错误信息
            return None

    def close_bn_position(
        self, symbol, side, positionSide, price_close, close_ratio=1.0
    ):
        """
        在币安期货市场平仓

        功能：执行平仓操作，支持重试机制确保成功
        参数：
            symbol: 交易对符号，如'BTCUSDT'
            side: 平仓方向，'BUY'或'SELL'
            positionSide: 持仓方向，'LONG'或'SHORT'
            price_close: 当前价格（用于通知）
            close_ratio: 平仓比例，1.0表示全部平仓，0.7表示平仓70%
            symbols_info: 交易对配置信息（精度等）
        """
        # 获取当前持仓数量
        amount = self.get_amount_close(symbol)
        if not amount:  # 0表示无持仓
            return
        close_ratio = 1 if amount * close_ratio * price_close < 10 else close_ratio
        # 计算实际平仓数量
        close_amount = amount * close_ratio
        close_amount = float(
            Decimal(str(close_amount)).quantize(
                self.symbols_info.get(symbol)["quantityPrecision"], rounding=ROUND_DOWN
            )
        )
        # 如果平仓数量为0，直接返回
        if close_amount <= 0:
            return

        # 循环平仓，直到完全平仓或失败
        while close_amount > 0:
            try:
                # 执行市价单平仓
                # 执行市价单平仓
                tx = self.um_futures_client.new_order(
                    symbol=symbol,
                    side=side,  # 平仓方向
                    type="MARKET",  # 市价单，立即成交
                    quantity=close_amount,  # 平仓数量
                    positionSide=positionSide,  # 持仓方向
                )
                # 尝试获取开仓价格，如果使用的是对象则获取entry_price，否则获取列表最后一个元素
                pos_data = self.alert_all["POSITIONS"].get(symbol)
                if pos_data and len(pos_data) >= 5:
                    entryPrice = pos_data[4]
                else:
                    entryPrice = price_close  # 无法获取时使用当前价格避免报错

                # 发送成功通知
                price_diff = (
                    price_close - entryPrice
                    if positionSide == PositionSide.LONG.value
                    else entryPrice - price_close
                )
                realized_pnl = price_diff * close_amount
                pnl_percent = price_diff / entryPrice if entryPrice != 0 else 0
                msg = f"{symbol}平仓\n持仓方向:{positionSide}\n委托价格:{price_close}\n委托数量:{tx.get('origQty', 0)}\n平仓比例:{close_ratio:.2%}\n平仓盈亏:{realized_pnl} USDT\n平仓收益:{pnl_percent:.2%}"
                self.send_msg(msg)
                return symbol  # 成功平仓，退出循环
            except Exception:
                # 平仓失败，等待后重试
                time.sleep(self.CLOSE_RETRY_DELAY)
                traceback.print_exc()  # 打印错误信息
                msg = f"bn平仓{symbol}失败，当前价格:{price_close}"
                self.send_msg(msg)
                # 重新获取持仓数量，可能部分平仓成功
                current_amount = self.get_amount_close(symbol)
                close_amount = current_amount * close_ratio
                close_amount = float(
                    Decimal(str(close_amount)).quantize(
                        self.symbols_info.get(symbol)["quantityPrecision"],
                        rounding=ROUND_DOWN,
                    )
                )
        return None

    async def check_bd(
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
                # 获取多空人数比数据
                long_short_ratio_data = await asyncio.to_thread(
                    self.um_futures_client.long_short_account_ratio,
                    symbol=symbol,
                    period="5m",
                    limit=self.KLINE_LIMIT,
                )
                # 提取最新的多空人数比
                if not long_short_ratio_data:
                    return False
                lsrd = float(long_short_ratio_data[-1]["longShortRatio"])

                # 根据持仓方向判断多空比条件
                if positionSide == PositionSide.LONG.value:
                    # 做多：要求多空比大于1（多头占优）
                    if lsrd <= 4 / 6:
                        return True
                    return False
                elif positionSide == PositionSide.SHORT.value:
                    # 做空：要求多空比小于1（空头占优）
                    if lsrd <= 1:
                        return False

                # 获取持仓量历史数据
                oi_1d = await asyncio.to_thread(
                    self.um_futures_client.open_interest_hist,
                    symbol=symbol,
                    period="1d",
                    limit=self.KLINE_LIMIT,
                )
                dtn_target = dtn.replace(hour=8, minute=0, second=0, microsecond=0)
                if oi_1d[-1]["timestamp"] != int(dtn_target.timestamp() * 1000):
                    return False
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
                    for index in range(-1, int(-len(kline_close) / 3) - 2, -1)
                )
            except Exception:
                traceback.print_exc()
                return False

    async def check_bz(
        self,
        semaphore,
        symbol,
    ):
        async with semaphore:
            try:
                # 获取多空人数比数据
                long_short_ratio_data = await asyncio.to_thread(
                    self.um_futures_client.long_short_account_ratio,
                    symbol=symbol,
                    period="5m",
                    limit=self.KLINE_LIMIT,
                )
                # 提取最新的多空人数比
                if not long_short_ratio_data:
                    return False
                lsrd = float(long_short_ratio_data[-1]["longShortRatio"])
                # 做多：要求多空比大于1（多头占优）
                if lsrd >= 1:
                    return False
                # 获取持仓量历史数据
                oi_5m = await asyncio.to_thread(
                    self.um_futures_client.open_interest_hist,
                    symbol=symbol,
                    period="5m",
                    limit=self.KLINE_LIMIT,
                )
                sumOpenInterestValue_5m = [
                    float(i["sumOpenInterestValue"]) for i in oi_5m
                ]  # 持仓价值（美元）
                sumOpenInterest_5m = [
                    float(i["sumOpenInterest"]) for i in oi_5m
                ]  # 持仓数量（合约数）

                oi_1d = await asyncio.to_thread(
                    self.um_futures_client.open_interest_hist,
                    symbol=symbol,
                    period="1d",
                    limit=2,
                )
                sumOpenInterestValue_1d = [
                    float(i["sumOpenInterestValue"]) for i in oi_1d
                ]  # 持仓价值（美元）
                sumOpenInterest_1d = [
                    float(i["sumOpenInterest"]) for i in oi_1d
                ]  # 持仓数量（合约数）

                if sumOpenInterest_5m[-1] <= min(
                    sumOpenInterest_1d[-2:]
                ) or sumOpenInterestValue_5m[-1] <= min(sumOpenInterestValue_1d[-2:]):
                    return False
                return True
            except Exception:
                traceback.print_exc()
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
            except Exception:
                print(f"{symbol}获取K线数据失败", flush=True)
                # 获取失败时返回空列表
                return []

    async def if_basis(self):
        """
        监控基差异常

        功能：实时监控期货与现货的基差，基差过大时发送警告
        基差 = 指数价格 / 市场价格
        - 基差 > 1：期货升水（期货价格高于现货）
        - 基差 < 1：期货贴水（期货价格低于现货）
        """
        BASIS = {}  # 记录每个交易对上次通知的时间
        while True:
            try:
                # 获取指数价格（现货价格）
                index_price = await asyncio.to_thread(
                    session.get,
                    url="https://fapi.binance.com/fapi/v1/premiumIndex",
                )
                index_price = {
                    ip["symbol"]: float(ip["indexPrice"]) for ip in index_price.json()
                }

                # 获取期货市场价格
                market_price = (
                    await asyncio.to_thread(
                        session.get,
                        url="https://fapi.binance.com/fapi/v2/ticker/price",
                    )
                ).json()
                time_now = time.time()

                # 遍历所有交易对，检查基差
                for p in market_price:
                    # 计算基差：指数价格 / 市场价格
                    # 基差 > 1 表示期货价格高于现货价格（升水）
                    # 基差 < 1 表示期货价格低于现货价格（贴水）
                    if (
                        basis := index_price.get(p["symbol"], float(p["price"]))
                        / float(p["price"])
                    ) > self.BASIS_WARNING_THRESHOLD and time_now - BASIS.get(
                        p["symbol"], 0
                    ) > self.BASIS_WARNING_COOLDOWN:
                        # 基差超过警告阈值且距离上次通知超过冷却时间，发送警告
                        BASIS[p["symbol"]] = time.time()
                        self.send_msg(
                            f"{p['symbol']} 基差超过{(self.BASIS_WARNING_THRESHOLD - 1) * 100:.1f}%：{basis * 100 - 100:.2%}",
                            True,
                        )
                    elif (
                        basis >= self.BASIS_ALERT_THRESHOLD
                        and time_now - BASIS.get(p["symbol"], 0)
                        > self.BASIS_ALERT_COOLDOWN
                    ):
                        # 基差超过异常阈值且距离上次通知超过冷却时间，发送异常提醒
                        BASIS[p["symbol"]] = time.time()
                        self.send_msg(
                            f"{p['symbol']} 基差异常：{basis * 100 - 100:.2%}", True
                        )
            except Exception:
                # 异常处理：打印错误信息但不中断监控
                traceback.print_exc()
            finally:
                # 每2秒检查一次
                await asyncio.sleep(self.RETRY_DELAY_SECONDS)

    def calculate_atr(self, kline_data, period=None):
        """
        计算ATR (平均真实波幅)
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

        if not tr_list:
            return 0.0
        # 简单移动平均计算ATR
        return sum(tr_list[-period:]) / min(len(tr_list), period)

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
            close_info_list = self.alert_all["POSITIONS"].get(symbol)
            open_info_list = self.alert_all["OBSERVATIONS"].get(symbol)

            close_info: Optional[Position] = (
                Position.from_list(close_info_list) if close_info_list else None
            )
            open_info: Optional[Observation] = (
                Observation.from_list(open_info_list) if open_info_list else None
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

            # 延迟获取15分钟K线
            kline_15 = None
            kline_close_15 = None
            kline_volume_15 = None

            async def get_kline_15_data():
                nonlocal kline_15, kline_close_15, kline_volume_15
                if kline_15 is None:
                    kline_15 = await self.get_kline(semaphore, symbol, "15m")
                    kline_close_15 = [k[4] for k in kline_15]
                    kline_volume_15 = [k[5] for k in kline_15]
                return kline_15, kline_close_15, kline_volume_15

            # 止盈止损计算辅助函数 (支持ATR)
            def calc_stop_profit_loss(price, is_long=True, atr=0):
                if atr <= 0:
                    return (0, 0)

                # ATR模式：使用类常量定义的倍数
                sl_dist = atr * self.ATR_STOP_LOSS_MULTIPLIER
                tp_dist = atr * self.ATR_TAKE_PROFIT_MULTIPLIER
                if is_long:
                    return (price + tp_dist, price - sl_dist)
                else:
                    # 做空：返回 (下界/止盈位, 上界/止损位)
                    return (price - tp_dist, price + sl_dist)

            # 检查现有持仓是否需要平仓
            if close_info:
                atr_value = self.calculate_atr(kline)

                # 检测是否需要用ATR初始化止盈止损 (止盈或止损为0表示需要更新)
                if (
                    close_info.take_profit == 0 or close_info.stop_loss == 0
                ) and atr_value > 0:
                    if close_info.position_side == PositionSide.LONG.value:
                        close_info.take_profit = close_info.entry_price + (
                            atr_value * self.ATR_TAKE_PROFIT_MULTIPLIER
                        )
                        close_info.stop_loss = close_info.entry_price - (
                            atr_value * self.ATR_STOP_LOSS_MULTIPLIER
                        )
                    elif close_info.position_side == PositionSide.SHORT.value:
                        close_info.take_profit = close_info.entry_price - (
                            atr_value * self.ATR_TAKE_PROFIT_MULTIPLIER
                        )
                        close_info.stop_loss = close_info.entry_price + (
                            atr_value * self.ATR_STOP_LOSS_MULTIPLIER
                        )
                    # 更新到字典
                    self.alert_all["POSITIONS"][symbol] = close_info.to_list()
                    print(
                        f"[ATR初始化] {symbol} 止盈:{close_info.take_profit:.2f} 止损:{close_info.stop_loss:.2f}",
                        flush=True,
                    )

                if current_price <= close_info.stop_loss:  # 触及止损
                    if close_info.position_side == PositionSide.SHORT.value:
                        self.close_bn_position(
                            symbol,
                            close_info.close_side.value,
                            close_info.position_side,  # 已经是字符串，不需要 .value
                            current_price,
                            0.5,
                        )
                        # 更新止盈止损并持久化到字典
                        if atr_value > 0:
                            new_tp, new_sl = calc_stop_profit_loss(
                                current_price, is_long=True, atr=atr_value
                            )
                            if new_tp > 0 and new_sl > 0:
                                close_info.take_profit = new_tp
                                close_info.stop_loss = new_sl

                        self.alert_all["POSITIONS"][symbol] = close_info.to_list()

                        # 转换为 Observation 对象并保存
                        new_obs = Observation(
                            price=current_price,
                            timestamp=current_timestamp,
                            side=OrderSide.SELL,
                            position_side="",
                        )
                        self.alert_all["OBSERVATIONS"][symbol] = new_obs.to_list()
                    else:
                        self.close_bn_position(
                            symbol,
                            close_info.close_side.value,
                            close_info.position_side,  # 已经是字符串，不需要 .value
                            current_price,
                            1,
                        )
                        self.alert_all["POSITIONS"].pop(symbol)

                        new_obs = Observation(
                            price=current_price,
                            timestamp=current_timestamp,
                            side=OrderSide.SELL,
                            position_side=PositionSide.BZ2.value,
                        )
                        self.alert_all["OBSERVATIONS"][symbol] = new_obs.to_list()

                elif current_price >= close_info.take_profit:  # 触及止盈
                    if close_info.position_side == PositionSide.LONG.value:
                        self.close_bn_position(
                            symbol,
                            close_info.close_side.value,
                            close_info.position_side,  # 已经是字符串，不需要 .value
                            current_price,
                            0.5,
                        )
                        # 更新止盈止损并持久化到字典
                        if atr_value > 0:
                            new_tp, new_sl = calc_stop_profit_loss(
                                current_price, is_long=True, atr=atr_value
                            )
                            if new_tp > 0 and new_sl > 0:
                                close_info.take_profit = new_tp
                                close_info.stop_loss = new_sl

                        self.alert_all["POSITIONS"][symbol] = close_info.to_list()

                        new_obs = Observation(
                            price=current_price,
                            timestamp=current_timestamp,
                            side=OrderSide.SELL,
                            position_side=PositionSide.BZ2.value,
                        )
                        self.alert_all["OBSERVATIONS"][symbol] = new_obs.to_list()
                    else:
                        self.close_bn_position(
                            symbol,
                            close_info.close_side.value,
                            close_info.position_side,  # 已经是字符串，不需要 .value
                            current_price,
                            1,
                        )
                        self.alert_all["POSITIONS"].pop(symbol)
                else:
                    # 更新动态止盈止损 (吊灯止损逻辑)
                    if atr_value > 0:
                        trailing_dist = atr_value * self.ATR_TRAILING_STOP_MULTIPLIER
                        if close_info.position_side == PositionSide.LONG.value:
                            # 移动止损：只上不下
                            new_sl = current_price - trailing_dist
                            new_tp = current_price + trailing_dist * 2
                            if new_sl > close_info.stop_loss:
                                close_info.stop_loss = new_sl
                            elif new_tp < close_info.take_profit:
                                close_info.take_profit = new_tp
                        elif close_info.position_side == PositionSide.SHORT.value:
                            # 移动止损：只下不上 (做空止损是上界/take_profit变量)
                            new_sl = current_price + trailing_dist
                            new_tp = current_price - trailing_dist * 2
                            if new_sl < close_info.take_profit:
                                close_info.take_profit = new_sl
                            elif new_tp > close_info.stop_loss:
                                close_info.stop_loss = new_tp
                    # 更新回字典
                    self.alert_all["POSITIONS"][symbol] = close_info.to_list()

            elif open_info:
                if (
                    open_info.position_side == PositionSide.BZ1.value
                    and current_timestamp - open_info.timestamp > self.ONE_DAY_SECONDS
                ):
                    self.alert_all["OBSERVATIONS"].pop(symbol)
                elif (
                    open_info.position_side == PositionSide.BZ2.value
                    and current_timestamp - open_info.timestamp > self.TEN_DAY_SECONDS
                ):
                    self.alert_all["OBSERVATIONS"].pop(symbol)
                else:
                    if not open_info.position_side:
                        return
                    should_open = False
                    await get_kline_15_data()
                    avg_close = sum(kline_close[-10:]) / len(kline_close[-10:])

                    if (
                        open_info.position_side == PositionSide.BZ1.value
                        and open_info.price < kline_close_15[-1]
                        and max(kline_close_15[:-1]) < kline_close_15[-1]
                        and kline_volume_15[-1]
                        > sum(kline_volume_15[:-2]) / len(kline_volume_15[:-2])
                        and self.calculate_chebyshev_probability(
                            kline_volume_15[:-2], max(kline_volume_15[-2:])
                        )["chebyshev_upper_bound"]
                        < self.CHEBYSHEV_EXTREME_THRESHOLD
                        and await self.check_bz(
                            semaphore,
                            symbol,
                        )
                    ):
                        if any(
                            kline_close_15[index] > max(kline_close_15[:index])
                            and kline_volume_15[index]
                            > sum(kline_volume_15[: index - 1])
                            / len(kline_volume_15[: index - 1])
                            and self.calculate_chebyshev_probability(
                                kline_volume_15[: index - 1],
                                max(kline_volume_15[index - 1 : index + 1]),
                            )["chebyshev_upper_bound"]
                            < self.CHEBYSHEV_EXTREME_THRESHOLD
                            for index in range(-3, int(-len(kline_15) / 3), -1)
                        ):
                            new_obs = Observation(
                                price=current_price,
                                timestamp=current_timestamp,
                                side=OrderSide.SELL,
                                position_side=PositionSide.BZ2.value,
                            )
                            self.alert_all["OBSERVATIONS"][symbol] = new_obs.to_list()
                            return
                        should_open = True
                    elif (
                        open_info.position_side == PositionSide.BZ2.value
                        and current_price > max(kline_close[-2], avg_close)
                        and kline_volume[-1]
                        > sum(kline_volume[-3:-1]) / len(kline_volume[-3:-1])
                        and self.calculate_chebyshev_probability(
                            kline_volume[-3:-1], kline_volume[-1]
                        )["chebyshev_upper_bound"]
                        < self.CHEBYSHEV_SIGNIFICANT_THRESHOLD
                        and current_timestamp - open_info.timestamp
                        >= self.ONE_DAY_SECONDS
                        and await self.check_bz(
                            semaphore,
                            symbol,
                        )
                    ):
                        if any(
                            (
                                kline_close[index] > kline_close[index - 1]
                                and kline_volume[index]
                                > sum(kline_volume[index - 2 : index])
                                / len(kline_volume[index - 2 : index])
                                and self.calculate_chebyshev_probability(
                                    kline_volume[index - 2 : index],
                                    kline_volume[index],
                                )["chebyshev_upper_bound"]
                                < self.CHEBYSHEV_SIGNIFICANT_THRESHOLD
                            )
                            for index in range(
                                -3,
                                int(
                                    (open_info.timestamp - current_timestamp)
                                    / self.ONE_DAY_SECONDS
                                ),
                                -1,
                            )
                        ):
                            self.alert_all["OBSERVATIONS"].pop(symbol)
                            return
                        should_open = True
                    if should_open:
                        atr_value = self.calculate_atr(kline)
                        zy, zs = calc_stop_profit_loss(
                            current_price, is_long=True, atr=atr_value
                        )
                        if zy == 0 and zs == 0:
                            return
                        rate_show = (
                            atr_value * self.ATR_STOP_LOSS_MULTIPLIER / current_price
                        )
                        self.send_msg(
                            f"==={symbol}**{open_info.position_side}**===\n价格:{kline_close_15[-1]}\n止盈:{zy}\n止损:{zs}\n收益率:{rate_show:.2%}"
                        )
                        if self.open_bn_position(
                            symbol, OrderSide.BUY.value, PositionSide.LONG.value, 0.1
                        ):
                            new_pos = Position(
                                take_profit=zy,
                                stop_loss=zs,
                                close_side=OrderSide.SELL,
                                position_side=PositionSide.LONG.value,
                                entry_price=current_price,
                            )
                            self.alert_all["POSITIONS"][symbol] = new_pos.to_list()
                            self.alert_all["OBSERVATIONS"].pop(symbol)
                            return

            else:
                # 做多信号判断
                if (
                    (
                        self.is_early_morning
                        or (
                            # 检查是否已有空头持仓
                            symbol not in self.alert_all["POSITIONS"]
                            or Position.from_list(
                                self.alert_all["POSITIONS"][symbol]
                            ).position_side
                            != PositionSide.LONG.value
                        )
                    )
                    and kline_close[-2] < current_price
                    and await self.check_bd(
                        semaphore,
                        symbol,
                        PositionSide.LONG.value,
                        kline_close,
                        kline_volume,
                        dtn,
                    )
                ):
                    if (
                        close_info
                        and close_info.position_side == PositionSide.SHORT.value
                    ):
                        self.close_bn_position(
                            symbol,
                            close_info.close_side.value,
                            close_info.position_side,  # 已经是字符串，不需要 .value
                            current_price,
                            1,
                        )
                    atr_value = self.calculate_atr(kline)
                    zy, zs = calc_stop_profit_loss(
                        current_price, is_long=True, atr=atr_value
                    )
                    if zy == 0 and zs == 0:
                        return
                    rate_show = (
                        atr_value * self.ATR_STOP_LOSS_MULTIPLIER / current_price
                    )
                    self.send_msg(
                        f"==={symbol}做多===\n价格:{current_price}\n止盈:{zy}\n止损:{zs}\n收益率:{rate_show:.2%}"
                    )
                    new_obs = Observation(
                        price=current_price,
                        timestamp=current_timestamp,
                        side=OrderSide.SELL,
                        position_side=PositionSide.BZ1.value,
                    )
                    self.alert_all["OBSERVATIONS"][symbol] = new_obs.to_list()

                # 做空信号判断
                elif (
                    (
                        self.is_early_morning
                        or (
                            symbol not in self.alert_all["POSITIONS"]
                            or Position.from_list(
                                self.alert_all["POSITIONS"][symbol]
                            ).position_side
                            != PositionSide.SHORT.value
                        )
                    )
                    and current_price < kline_close[-2]
                    and await self.check_bd(
                        semaphore,
                        symbol,
                        PositionSide.SHORT.value,
                        kline_close,
                        kline_volume,
                        dtn,
                    )
                ):
                    if (
                        close_info
                        and close_info.position_side == PositionSide.LONG.value
                    ):
                        self.close_bn_position(
                            symbol,
                            close_info.close_side.value,
                            close_info.position_side,  # 已经是字符串，不需要 .value
                            current_price,
                            1,
                        )
                    atr_value = self.calculate_atr(kline)
                    zy, zs = calc_stop_profit_loss(
                        current_price, is_long=False, atr=atr_value
                    )
                    if zy == 0 and zs == 0:
                        return
                    rate_show = (
                        atr_value * self.ATR_STOP_LOSS_MULTIPLIER / current_price
                    )
                    self.send_msg(
                        f"==={symbol}**BD**===\n价格:{current_price}\n止盈:{zy}\n止损:{zs}\n收益率:{rate_show:.2%}"
                    )
                    if self.open_bn_position(
                        symbol, OrderSide.SELL.value, PositionSide.SHORT.value, 0.1
                    ):
                        new_pos = Position(
                            take_profit=zs,  # 做空止损是上界
                            stop_loss=zy,  # 做空止盈是下界
                            close_side=OrderSide.BUY,
                            position_side=PositionSide.SHORT.value,
                            entry_price=current_price,
                        )
                        self.alert_all["POSITIONS"][symbol] = new_pos.to_list()
        except Exception:
            traceback.print_exc()
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
            positions_data.append(
                f"==={p['symbol']}===\n开仓价格:{entryPrice} USDT\n持仓方向:{p['positionSide']}\n名义价值:{p['notional']} USDT\n持仓盈亏:{p['unRealizedProfit']} USDT\n持仓收益:{float(p['unRealizedProfit']) / abs(float(p['notional'])):.2%}"
            )

            if p["symbol"] not in self.alert_all["POSITIONS"]:
                # 发现未记录的持仓,止盈止损暂设为0,等待rzq_token用ATR更新
                if p["positionSide"] == PositionSide.LONG.value:
                    new_pos = Position(
                        take_profit=0,  # 标记:需要ATR更新
                        stop_loss=0,  # 标记:需要ATR更新
                        close_side=OrderSide.SELL,
                        position_side=PositionSide.LONG.value,
                        entry_price=entryPrice,
                    )
                    self.alert_all["POSITIONS"][p["symbol"]] = new_pos.to_list()
                else:
                    new_pos = Position(
                        take_profit=0,  # 标记:需要ATR更新
                        stop_loss=0,  # 标记:需要ATR更新
                        close_side=OrderSide.BUY,
                        position_side=PositionSide.SHORT.value,
                        entry_price=entryPrice,
                    )
                    self.alert_all["POSITIONS"][p["symbol"]] = new_pos.to_list()
            else:
                # 更新现有持仓的开仓价格
                # 先转换为对象，更新属性，再转换回列表
                current_pos_list = self.alert_all["POSITIONS"][p["symbol"]]
                # 兼容旧数据：如果列表长度小于5，说明缺少entry_price，from_list会自动处理
                pos_obj = Position.from_list(current_pos_list)
                pos_obj.entry_price = entryPrice
                self.alert_all["POSITIONS"][p["symbol"]] = pos_obj.to_list()

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
            await asyncio.wait_for(self._rzq_market_impl(market), timeout=300)
        except asyncio.TimeoutError:
            error_msg = f"{market} 市场分析任务超时(5分钟)，已强制中断"
            print(f"[{datetime.datetime.now()}] {error_msg}", flush=True)
            self.send_msg(error_msg)
        except Exception as e:
            error_msg = f"{market} 市场分析任务异常: {str(e)}"
            print(f"[{datetime.datetime.now()}] {error_msg}", flush=True)
            traceback.print_exc()
            self.send_msg(error_msg)

    async def _rzq_market_impl(self, market):
        """市场分析的实际实现"""
        now = datetime.datetime.now()
        self.is_early_morning = now.hour == 8 and now.minute == 0

        # 重试机制：最多尝试10次获取交易对信息
        if now.minute % 15 == 0 or not self.symbols:
            for i in range(10):
                try:
                    positions_data = self.get_position_risk()
                    self.get_symbols_info()
                    self.symbols = list(self.symbols_info.keys())
                    break  # 成功获取，退出重试循环
                except Exception:
                    # 获取失败，等待后重试
                    traceback.print_exc()
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)
        if self.is_early_morning:
            balance = self.um_futures_client.account()["totalWalletBalance"]
            self.send_msg(f"账户余额:\n{balance} USDT\n持仓信息:\n{positions_data}")
            print(f"[{datetime.datetime.now()}] 账户信息推送任务执行完成", flush=True)
        # 创建信号量，限制最大并发数，避免API限制
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
        print(now, f"{market}任务开始 - 总交易对数量: {len(self.symbols)}", flush=True)

        success = set()  # 记录成功处理的交易对
        chunk_size = self.CHUNK_SIZE  # 分批处理，避免内存占用过高
        # symbols = ["OGUSDT"]
        # 分批处理所有交易对
        for i in range(0, len(self.symbols), chunk_size):
            symbol_chunk = self.symbols[i : i + chunk_size]  # 当前批次的交易对
            # 创建异步任务列表
            tasks = [
                self.rzq_token(semaphore, symbol, success, now)
                for symbol in symbol_chunk
            ]
            # 等待当前批次所有任务完成
            await asyncio.gather(*tasks)
            gc.collect()  # 垃圾回收，释放内存

        # 打印任务完成信息
        print(
            datetime.datetime.now(),
            f"{market}任务结束 - 总交易对数量: {len(success)}",
            self.alert_all,
            flush=True,
        )
        if self.alert_all != self.alert_all_old:
            self.get_position_risk()
            self.alert_all_old = copy.deepcopy(self.alert_all)
            # 保存分析结果到文件
            with open(self.alert_all_file, "w") as f:
                json.dump(self.alert_all, f, ensure_ascii=False, indent=4)


class AUTOA:
    # ==================== ATR风控常量 ====================
    ATR_PERIOD = 10  # ATR计算周期
    ATR_STOP_LOSS_MULTIPLIER = 2.0  # ATR止损倍数
    ATR_TAKE_PROFIT_MULTIPLIER = 4.0  # ATR止盈倍数 (盈亏比1:2)
    ATR_TRAILING_STOP_MULTIPLIER = 1.5  # ATR移动止损倍数

    # ==================== 切比雪夫概率阈值常量 ====================
    CHEBYSHEV_EXTREME_THRESHOLD = 0.01  # 极端异常阈值（1%），用于检测非常罕见的事件
    CHEBYSHEV_SIGNIFICANT_THRESHOLD = 0.25  # 显著异常阈值（25%），用于检测显著的异常

    # ==================== 时间常量 ====================
    ONE_DAY_SECONDS = 24 * 60 * 60  # 一天的秒数
    OBSERVATION_TIMEOUT_DAYS = 10  # 观察超时天数

    qy_key = "6f2ec864-c474-4c8f-b069-1e3c35eb7d73"
    alert_all_file = "alert_all_A.json"
    alert_all = json.load(open(alert_all_file, "r", encoding="utf-8"))
    alert_all_old = copy.deepcopy(alert_all)
    zt_dates = []
    hist_cache = {}

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

        功能：通过企业微信或微信发送交易通知消息
        参数：
            msg: 要发送的消息内容
            wx: 是否使用微信发送（True=微信，False=企业微信）
        """
        try:
            # 记录发送时间，便于调试和追踪
            current_time = datetime.datetime.now()
            print(f"{current_time} - 发送消息: {msg}", flush=True)
            # 企业微信发送格式：使用企业微信机器人webhook
            json_msg = {"msgtype": "text", "text": {"content": msg}}
            response = session.post(
                url=f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={cls.qy_key}",
                json=json_msg,
            )

            # 检查发送结果，失败时记录状态码
            if response.status_code != 200:
                print(f"消息发送失败，状态码: {response.status_code}", flush=True)
        except Exception as e:
            # 异常处理：记录错误但不中断程序运行
            print(f"消息发送异常: {str(e)}", flush=True)

    @staticmethod
    def get_last_trading_days(today=None, days=30):
        """
        获取A股交易日历

        功能：从新浪财经获取A股交易日历，用于股票筛选
        参数：
            today: 指定日期，默认为当前日期
            days: 获取最近交易日的天数，默认为60天
        返回：
            (start_date, end_date, zt_date): 起始日期、结束日期、涨停股查询日期列表
        """
        # 设置默认日期为今天
        if not today:
            today = datetime.datetime.today()

        try:
            # 从新浪财经获取交易日历
            trade_dates = ak.tool_trade_date_hist_sina()
            trade_dates = pd.to_datetime(trade_dates["trade_date"])

            # 过滤出不晚于指定日期的交易日
            valid_dates = trade_dates[trade_dates <= today]

            if valid_dates.empty:
                print(f"警告: 未找到 {today} 之前的交易日", flush=True)
                return None, None, []

            # 获取指定日期前的最近n个交易日，按时间降序排列
            recent_trading_days = valid_dates.sort_values(ascending=False).iloc[:days]

            # 选择第3天到第10天的交易日作为涨停股查询日期（避开最近的波动）
            return [i.strftime("%Y-%m-%d") for i in recent_trading_days.iloc]
        except Exception as e:
            print(f"获取交易日历失败: {str(e)}", flush=True)
            return None, None, []

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
            if code in cls.hist_cache:
                data_list = copy.deepcopy(cls.hist_cache[code])
            else:

                def fetch_bs_data(stock_code_pre, stock_code):
                    rs = bs.query_history_k_data_plus(
                        f"{stock_code_pre}.{stock_code}",  # 股票代码
                        fields,
                        start_date=start_date,
                        end_date=end_date,
                        frequency=frequency,  # 日K
                        adjustflag=adjustflag,  # 3：前复权；1：不复权；2：后复权
                    )
                    dl = []
                    while (rs.error_code == "0") & rs.next():
                        dl.append(rs.get_row_data())
                    return dl

                data_list = await loop.run_in_executor(
                    None, fetch_bs_data, code_pre, code
                )
                if data_list:
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
            hist["close"] = pd.to_numeric(hist["close"], errors="coerce")
            hist["volume"] = pd.to_numeric(hist["volume"], errors="coerce")
            hist["preclose"] = pd.to_numeric(hist["preclose"], errors="coerce")
            hist["涨跌幅"] = (hist["close"] - hist["preclose"]) / hist["preclose"]
            return hist
        except Exception:
            traceback.print_exc()
            return pd.DataFrame()

    @classmethod
    async def on_positions(cls, code, zt_dates, close_info, today):
        """
        处理持仓列表中的股票，检测平仓信号

        策略：止盈止损 - 当价格触及止盈或止损线时平仓
        核心逻辑：
            - 止盈触发：当前价 >= 止盈价
            - 止损触发：当前价 <= 止损价
            - 触发后将股票移至观察列表（BZ2策略会发送通知）

        参数：
            code: 股票代码（如'000001'）
            zt_dates: 交易日期列表
            close_info: 持仓记录 [止盈, 止损, 股票名称, 日期, 策略标签]
            today: 当前日期时间
        """
        if int(today.strftime("%Y%m%d")) <= close_info[3]:
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
        if price_close <= close_info[1] or price_close >= close_info[0]:
            # 将股票移至观察列表（记录平仓价格和时间）
            cls.alert_all["OBSERVATIONS"][code] = [
                price_close,
                today.timestamp(),
                close_info[2],  # 股票名称
                "LONG",  # 观察方向（默认LONG）
            ]

            # 从持仓列表移除
            cls.alert_all["POSITIONS"].pop(code)

            # 发送平仓通知（仅BZ2策略需要通知）
            if close_info[-1] == "BZ2":
                profit_rate = (
                    (price_close / close_info[4] - 1) if close_info[4] > 0 else 0
                )
                msg = f"{close_info[2]} 平仓\n委托价格:{price_close:.2f}\n平仓收益:{profit_rate:.2%}"
                cls.send_msg(msg)
        else:
            # 未触及止盈止损，执行移动止损逻辑 (吊灯止损)
            atr = cls.calculate_atr(hist)
            if atr > 0:
                # 移动止损：价格 - 1.5 * ATR
                trailing_sl = price_close - (atr * 1.5)
                # 只有当新止损位高于旧止损位时才更新 (只上不下)
                if trailing_sl > close_info[1]:
                    close_info[1] = trailing_sl
                    # 如果价格创新高，也可以选择更新entry_price作为参考(可选)
                    if price_close > close_info[4]:
                        close_info[4] = price_close

                    # 更新回字典
                    cls.alert_all["POSITIONS"][code] = close_info
                    # 可选：发送移动止损通知
                    # cls.send_msg(f"{close_info[2]} 移动止损更新\n现价:{price_close:.2f}\n新止损:{trailing_sl:.2f}(前值:{old_sl:.2f})")

    @classmethod
    async def on_observations(cls, code, zt_dates, open_info, today):
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
            open_info: 观察记录 [价格, 时间戳, 股票名称, 仓位方向]
            today: 当前日期时间
        """
        # 获取股票历史数据（前复权，确保价格连续性）
        hist = await cls.stock_zh_a_hist(
            code,
            "date,code,open,high,low,close,preclose,volume,amount",
            start_date=zt_dates[-1],
            end_date=zt_dates[0],
            frequency="d",
            adjustflag="3",  # 前复权
        )

        # 数据校验：无历史数据则跳过
        if hist.empty:
            return

        # 获取最新价格
        price_close = float(hist.iloc[-1]["close"])

        # 超时清理：观察超过10天的股票移出观察列表
        observation_duration = today.timestamp() - open_info[1]
        if observation_duration > cls.OBSERVATION_TIMEOUT_DAYS * cls.ONE_DAY_SECONDS:
            cls.alert_all["OBSERVATIONS"].pop(code)
            return

        # 信号检测：检查是否满足买入条件
        # 条件1：观察至少24小时（避免当天冲动）
        # 条件2：价格突破关键阻力位（10日均价、昨收、今开）
        # 条件3：成交量显著放大（确认突破有效性）
        if observation_duration >= cls.ONE_DAY_SECONDS:
            # 计算关键价格阻力位
            resistance_price = max(
                float(hist.iloc[-2]["close"]),  # 昨日收盘价
                float(hist.iloc[-1]["open"]),  # 今日开盘价
                float(hist.iloc[-10:]["close"].mean()),  # 10日均价
            )

            # 判断是否满足买入条件
            price_breakout = price_close > resistance_price
            volume_breakout = (
                hist.iloc[-1]["volume"] > hist["volume"].iloc[-3:-1].mean()
                and cls.calculate_chebyshev_probability(
                    hist["volume"].iloc[-3:-1], hist.iloc[-1]["volume"]
                )["chebyshev_upper_bound"]
                < cls.CHEBYSHEV_SIGNIFICANT_THRESHOLD
            )

            if price_breakout and volume_breakout:
                # ========== 计算止盈止损（ATR动态方法） ==========

                # 1. 计算ATR（平均真实波幅）
                atr = cls.calculate_atr(hist)
                atr_percent = (atr / price_close) if price_close > 0 else 0

                # 3. 动态止盈止损：ATR模式 (止损2x, 止盈4x)
                if atr > 0:
                    stop_loss_dist = atr * cls.ATR_STOP_LOSS_MULTIPLIER
                    take_profit_dist = atr * cls.ATR_TAKE_PROFIT_MULTIPLIER

                    take_profit = price_close + take_profit_dist
                    stop_loss = price_close - stop_loss_dist

                    # 4. 记录到持仓列表
                    cls.alert_all["POSITIONS"][code] = [
                        take_profit,
                        stop_loss,
                        open_info[2],  # 股票名称
                        int(today.strftime("%Y%m%d")),  # 买入日期
                        price_close,
                        "BZ2",  # 策略标签：BZ2=观察列表突破买入
                    ]

                    # 5. 从观察列表移除
                    cls.alert_all["OBSERVATIONS"].pop(code)

                    # 6. 发送买入通知
                    msg = (
                        f"==={open_info[2]}**BZ2**===\n"
                        f"价格:{price_close:.2f}\n"
                        f"止盈:{take_profit:.2f}\n"
                        f"止损:{stop_loss:.2f}\n"
                        f"收益率:{atr_percent:.2%}\n"
                    )
                    cls.send_msg(msg)

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
        if (
            cls.zt_dates
            and today.strftime("%Y-%m-%d") not in cls.zt_dates
            or today.hour >= 15
            and today.minute >= 1
        ):
            return []
        if not cls.zt_dates:
            cls.zt_dates = cls.get_last_trading_days(today)
        selected = set()  # 存储符合条件的股票
        if today.hour == 15:
            zt_df = ak.stock_zt_pool_em(date=cls.zt_dates[0].replace("-", ""))
            stock_codes = zt_df[["代码", "名称", "连板数"]].values.tolist()
            for code in stock_codes:
                if (
                    code[2] == 1
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

                    # 使用ATR计算止盈止损
                    atr = cls.calculate_atr(hist)
                    if atr > 0:
                        zy = price_close + (atr * cls.ATR_TAKE_PROFIT_MULTIPLIER)
                        zs = price_close - (atr * cls.ATR_STOP_LOSS_MULTIPLIER)
                        rate_show = (atr * cls.ATR_STOP_LOSS_MULTIPLIER) / price_close

                        selected.add(
                            f"==={code[1]}===\n价格:{price_close}\n止盈:{zy}\n止损:{zs}\n收益率:{rate_show:.2%}"
                        )
                        # 记录到持仓列表：[止盈, 止损, 股票名称, 日期, 策略标签]
                        cls.alert_all["POSITIONS"][code[0]] = [
                            zy,
                            zs,
                            code[1],  # 股票名称
                            int(today.strftime("%Y%m%d")),  # 买入日期
                            price_close,
                            "BZ1",  # 策略标签：BZ1=涨停次日买入
                        ]
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
            # 设置超时时间为3分钟，防止任务卡住
            await asyncio.wait_for(cls._monitor_stocks_impl(), timeout=600)
        except asyncio.TimeoutError:
            error_msg = "A股监控任务超时(3分钟)，已强制中断"
            print(f"[{datetime.datetime.now()}] {error_msg}", flush=True)
            cls.send_msg(error_msg)
        except Exception as e:
            error_msg = f"A股监控任务异常: {str(e)}"
            print(f"[{datetime.datetime.now()}] {error_msg}", flush=True)
            traceback.print_exc()
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
            print(f"符合量能条件的股票：{filtered}", flush=True)

            # 如果有符合条件的股票，发送通知
            if filtered:
                # 构建消息内容
                content = f"===A{len(filtered)} BZ1===\n" + "\n-------\n".join(filtered)
                # 发送到企业微信群
                cls.send_msg(content)

            if cls.alert_all != cls.alert_all_old:
                cls.alert_all_old = copy.deepcopy(cls.alert_all)
                # 保存分析结果到文件
                with open(cls.alert_all_file, "w", encoding="utf-8") as f:
                    json.dump(cls.alert_all, f, ensure_ascii=False, indent=4)
        finally:
            # 确保总是登出，即使发生异常（使用异步执行）
            await loop.run_in_executor(None, bs.logout)


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
        print("警告: 未设置环境变量 QY_WECHAT_KEY，消息通知功能将不可用", flush=True)
        # 可以选择：1) 抛出异常退出  2) 使用空密钥继续运行
        # 这里选择继续运行但禁用通知
        qy_key = ""

    autobn = AUTOBN.from_cfg(
        bn_api_file=os.path.join(current_dir, "bn.json"),
        alert_all_file=os.path.join(current_dir, "alert_all.json"),
        qy_key=qy_key,
    )

    # 初始化任务调度器
    scheduler = AsyncIOScheduler()

    print("配置A股监控任务...", flush=True)
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

    print("配置币安市场分析任务...", flush=True)
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

    print("启动调度器...", flush=True)
    # 启动调度器
    scheduler.start()
    print("调度器已启动，等待任务触发...", flush=True)

    # 创建一个永不触发的事件，使程序一直运行
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发（实际不会发生）


if __name__ == "__main__":
    """
    程序入口：初始化配置并启动主程序

    功能：初始化所有必要的配置和客户端，然后启动主程序
    """
    print("autoBN启动", flush=True)
    # 启动主程序（调度器在main函数中初始化）
    asyncio.run(main())
