# 导入必要的库
import asyncio  # 异步编程库，用于并发处理
import copy
import datetime  # 日期时间处理
import gc  # 垃圾回收，用于内存管理
import json  # JSON数据处理
import os  # 操作系统接口，用于环境变量
import time  # 时间相关函数
import traceback  # 异常追踪
from decimal import Decimal, ROUND_DOWN  # 精确数值计算
from binance.um_futures import UMFutures  # 币安期货API客户端
import akshare as ak  # A股数据获取库
import pandas as pd  # 数据分析库
import requests  # HTTP请求库
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # 异步任务调度器


class AUTOBN:
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
        obj.leverage = kwargs.get("leverage", 3)
        obj.health4open = kwargs.get("health4open", 70)
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

        # HTTP 会话配置（可覆盖）
        obj.session = kwargs.get("session") or requests.Session()
        obj.session.verify = kwargs.get("session_verify", False)
        obj.session.headers = kwargs.get(
            "session_headers", {"Content-Type": "application/json"}
        )

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
        # 说明：若传入 api_key/api_secret，将覆盖 bn_api_file 中的值
        with open(bn_api_file, "r") as f:
            bn_api = json.load(f)
        api_key = kwargs.get(
            "api_key",
            bn_api.get(
                "api_key",
                "Uz3Tat0QcGBYRa9E2TQZn1nscd0iNcoEnpDbk71q2uEke3jC8d9NADQCUoXLmkn2",
            ),
        )
        api_secret = kwargs.get(
            "api_secret",
            bn_api.get(
                "api_secret",
                "tqCsBnIj3T9BuZYnwyHJTNVWwL88LA1PQtZHqh3wVV6kWbWRRLyWEfrDknvdm09J",
            ),
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

    def send_msg(self, msg, wx=False):
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
                response = self.session.post(
                    f"http://wechatpadpro:1238/message/SendTextMessage?key={self.wx_key}",
                    json=json_msg,
                )
            else:
                # 企业微信发送格式：使用企业微信机器人webhook
                json_msg = {"msgtype": "text", "text": {"content": msg}}
                response = self.session.post(
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

        # 加上新增头寸的维持保证金（按0.4%计算）
        total_maintenance_margin += notional * 0.004

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
            # 策略2：实际开仓金额不超过槽位和总资金70%的较小值
            safe_balance = min(self.slot_balance[0], balance * 0.7)

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

            # 最小交易额检查（币安要求最低6 USDT）
            if notional < 6:
                self.send_msg(
                    f"{symbol} 开仓失败：交易额 {notional} 低于最小要求 6 USDT"
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
                tx = self.um_futures_client.new_order(
                    symbol=symbol,
                    side=side,  # 平仓方向
                    type="MARKET",  # 市价单，立即成交
                    quantity=close_amount,  # 平仓数量
                    positionSide=positionSide,  # 持仓方向
                )
                entryPrice = self.alert_all["POSITIONS"][symbol][-1]
                # 发送成功通知
                price_diff = (
                    price_close - entryPrice
                    if positionSide == "LONG"
                    else entryPrice - price_close
                )
                realized_pnl = price_diff * close_amount
                pnl_percent = price_diff / entryPrice
                msg = f"{symbol}平仓\n持仓方向:{positionSide}\n委托价格:{price_close}\n委托数量:{tx.get('origQty', 0)}\n平仓比例:{close_ratio * 100:.0f}%\n平仓盈亏:{realized_pnl} USDT\n平仓收益:{pnl_percent * self.leverage * 100:.2f}%"
                self.send_msg(msg)
                return symbol  # 成功平仓，退出循环
            except Exception:
                # 平仓失败，等待3秒后重试F
                time.sleep(3)
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

    async def increase_oi(
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

        功能：分析持仓量变化和多空比，判断市场情绪和资金流向
        参数：
            semaphore: 异步信号量，控制并发数量
            symbol: 交易对符号，如'BTCUSDT'
            positionSide: 持仓方向，'LONG'或'SHORT'
            kline_close: K线收盘价列表，可选参数
        返回：
            True表示适合开仓，False表示不适合
        """
        async with semaphore:
            try:
                if positionSide == "LONG":
                    # 做多条件检查：需要持仓量增加且多空比小于1（空头占优）
                    # 条件1：最新持仓量必须大于前3天最大值（说明有资金流入）
                    return True
                else:
                    # 获取持仓量历史数据（30天）
                    oi_1d = await asyncio.to_thread(
                        self.um_futures_client.open_interest_hist,
                        symbol=symbol,
                        period="1d",
                        limit=30,
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

                    # 获取多空比历史数据（100天）
                    # lsar = await asyncio.to_thread(self.um_futures_client.long_short_account_ratio, symbol=symbol,
                    #                                period="1d", limit=30)
                    # lsar = [float(i['longShortRatio']) for i in lsar]  # 多空比列表

                    # 打印分析数据，便于监控和调试
                    # print(
                    #     f"{symbol} 增仓信号{max(sumOpenInterest_1d[-3:-1])}——>{sumOpenInterest_1d[-1]} ${max(sumOpenInterestValue_1d[-3:-1])}——>${sumOpenInterestValue_1d[-1]}",
                    #     flush=True,
                    # )
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

    async def decrease_oi(
        self,
        semaphore,
        symbol,
        positionSide,
        kline_close=None,
    ):
        """
        检查减仓信号，判断是否应该平仓

        功能：分析持仓量变化，判断获利了结或止损时机
        参数：
            semaphore: 异步信号量，控制并发数量
            symbol: 交易对符号，如'BTCUSDT'
            positionSide: 持仓方向，'LONG'或'SHORT'
        返回：
            True表示应该平仓，False表示继续持有
        """
        async with semaphore:
            try:
                # 获取持仓量历史数据（30天）
                oi_5m = await asyncio.to_thread(
                    self.um_futures_client.open_interest_hist,
                    symbol=symbol,
                    period="5m",
                    limit=1,
                )
                sumOpenInterestValue_5m = [
                    float(i["sumOpenInterestValue"]) for i in oi_5m
                ]  # 持仓价值（美元）
                sumOpenInterest_5m = [
                    float(i["sumOpenInterest"]) for i in oi_5m
                ]  # 持仓数量（合约数）

                # 打印减仓信号数据，便于监控
                # print(
                #     f"{symbol} 减仓信号{sumOpenInterest_5m[-2]}——>{sumOpenInterest_5m[-1]} ${sumOpenInterestValue_5m[-2]}——>${sumOpenInterestValue_5m[-1]}",
                #     flush=True,
                # )
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
                if sumOpenInterest_5m[-1] <= max(
                    sumOpenInterest_1d[-2:]
                ) or sumOpenInterestValue_5m[-1] <= max(sumOpenInterestValue_1d[-2:]):
                    return False
                if positionSide == "LONG":
                    return True
                else:
                    for index in range(-1, -len(kline_close), -1):
                        # 如果持仓量和价值都增加，说明是正常增仓，继续等待
                        if kline_close[index - 1] > max(kline_close[: index - 1]):
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
                # 异步获取K线数据（30根K线）
                kline = await asyncio.to_thread(
                    self.um_futures_client.klines,
                    symbol=symbol,
                    interval=interval,
                    limit=30,
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
                    self.session.get,
                    url="https://fapi.binance.com/fapi/v1/premiumIndex",
                )
                index_price = {
                    ip["symbol"]: float(ip["indexPrice"]) for ip in index_price.json()
                }

                # 获取期货市场价格
                market_price = (
                    await asyncio.to_thread(
                        self.session.get,
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
                    ) > 1.02 and time_now - BASIS.get(p["symbol"], 0) > 60:
                        # 基差超过2%且距离上次通知超过60秒，发送警告
                        BASIS[p["symbol"]] = time.time()
                        self.send_msg(
                            f"{p['symbol']} 基差超过2%：{basis * 100 - 100:.2f}%", True
                        )
                    elif basis >= 1.015 and time_now - BASIS.get(p["symbol"], 0) > 180:
                        # 基差超过1.5%且距离上次通知超过180秒，发送异常提醒
                        BASIS[p["symbol"]] = time.time()
                        self.send_msg(
                            f"{p['symbol']} 基差异常：{basis * 100 - 100:.2f}%", True
                        )
            except Exception:
                # 异常处理：打印错误信息但不中断监控
                traceback.print_exc()
            finally:
                # 每2秒检查一次
                await asyncio.sleep(2)

    async def rzq_token(self, semaphore, symbol, success, dtn):
        """
        核心交易逻辑：分析K线数据并执行交易决策

        功能：这是整个交易系统的核心函数，负责：
        1. 获取K线数据
        2. 检查现有持仓是否需要平仓
        3. 分析市场信号决定是否开仓
        4. 执行开仓操作

        参数：
            semaphore: 异步信号量，控制并发数量
            symbol: 交易对符号，如'BTCUSDT'
            success: 成功处理的交易对集合
            symbols_info: 交易对配置信息
        """
        try:
            close_info = self.alert_all["POSITIONS"].get(symbol)
            open_info = self.alert_all["OBSERVATIONS"].get(symbol)
            dtn_minute = dtn.minute % 4 == 0
            if not close_info and not open_info and not dtn_minute:
                return
            # 获取日K线数据（30天）
            kline = await self.get_kline(semaphore, symbol, "1Dutc")
            success.add(symbol)  # 记录成功处理的交易对

            # 数据量检查：至少需要4根K线进行分析
            if len(kline) < 4:
                return
            kline_close = [k[4] for k in kline]  # 提取收盘价列表
            kline_zf = sum(
                list(map(lambda k: abs(k[4] / k[1] - 1), kline[-10:]))
            ) / len(kline[-10:])
            # 检查现有持仓是否需要平仓
            if close_info:
                # close_info格式：[止盈价, 止损价, 平仓方向, 持仓方向]
                # 平仓条件：价格触及止损/止盈 或 减仓信号触发
                if (
                    kline_close[-1] <= close_info[1]
                    or close_info[3] == "LONG"
                    and kline_close[-1]
                    < sum(kline_close[-10:]) / len(kline_close[-10:])
                ):
                    if close_info[3] == "SHORT":
                        self.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 0.5
                        )
                        close_info[1] = kline_close[-1] * (1 - kline_zf * 0.5)
                        close_info[0] = kline_close[-1] * (1 + kline_zf * 0.5)
                    else:
                        self.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 1
                        )
                        self.alert_all["POSITIONS"].pop(symbol)
                        self.alert_all["OBSERVATIONS"][symbol] = [
                            kline_close[-1],
                            time.time(),
                            "SELL",
                            "SHORT",
                        ]
                elif kline_close[-1] >= close_info[0]:
                    if close_info[3] == "LONG":
                        self.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 0.5
                        )
                        close_info[0] = kline_close[-1] * (1 + kline_zf * 0.5)
                        close_info[1] = kline_close[-1] * (1 - kline_zf * 0.5)
                        self.alert_all["OBSERVATIONS"][symbol] = [
                            kline_close[-1],
                            time.time(),
                            "SELL",
                            "SHORT",
                        ]
                    else:
                        self.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 1
                        )
                        self.alert_all["POSITIONS"].pop(symbol)
            elif open_info:
                if time.time() - open_info[1] > 24 * 60 * 60:
                    self.alert_all["OBSERVATIONS"].pop(symbol)
                else:
                    kline_15 = await self.get_kline(semaphore, symbol, "15m")
                    kline_close_15 = [k[4] for k in kline_15]  # 提取收盘价列表
                    kline_volume_15 = [k[5] for k in kline_15]  # 提取成交量列表
                    if (
                        open_info[3] == "LONG"
                        and open_info[0] < kline_close_15[-1]
                        and max(kline_close_15[:-1]) < kline_close_15[-1]
                        and max(kline_volume_15[:-1]) < kline_volume_15[-1]
                        and sum(kline_volume_15[: -int(len(kline_volume_15) * 2 / 3)])
                        / len(kline_volume_15[: -int(len(kline_volume_15) * 2 / 3)])
                        * 9
                        < kline_volume_15[-1]
                        and await self.decrease_oi(
                            semaphore,
                            symbol,
                            open_info[3],
                            kline_close_15,
                        )
                    ):
                        zy = kline_close[-1] * (1 + kline_zf)
                        zs = kline_close[-1] * (1 - kline_zf)
                        self.send_msg(
                            f"==={symbol}**BZ1**===\n价格:{kline_close_15[-1]}\n止盈:{zy}\n止损:{zs}"
                        )
                        if self.open_bn_position(symbol, "BUY", "LONG", 0.1):
                            self.alert_all["POSITIONS"][symbol] = [
                                zy,
                                zs,
                                "SELL",
                                "LONG",
                            ]
                            self.alert_all["OBSERVATIONS"].pop(symbol)
                            return
                    elif (
                        open_info[3] == "SHORT"
                        and kline_close_15[-1] > open_info[0]
                        and max(kline_volume_15[-3:-1]) < kline_volume_15[-1]
                        and await self.decrease_oi(
                            semaphore,
                            symbol,
                            open_info[3],
                            kline_close_15,
                        )
                    ):
                        # 设置止盈止损：止盈9%，止损9%
                        zy = kline_close[-1] * (1 + kline_zf * 0.5)
                        zs = kline_close[-1] * (1 - kline_zf * 0.5)
                        self.send_msg(
                            f"==={symbol}**BZ2**===\n价格:{kline_close_15[-1]}\n止盈:{zy}\n止损:{zs}"
                        )
                        if self.open_bn_position(symbol, "BUY", "LONG", 0.1):
                            self.alert_all["POSITIONS"][symbol] = [
                                zy,
                                zs,
                                "SELL",
                                "LONG",
                            ]
                            self.alert_all["OBSERVATIONS"].pop(symbol)
                            return
            elif dtn_minute:
                # 计算每日涨跌幅：(收盘价 - 开盘价) / 开盘价
                kline_volume = [k[5] for k in kline]
                # 做多信号判断：需要同时满足以下条件
                # 条件1：价格连续上涨（前3天 < 前2天 < 前1天）
                # 条件2：成交量放大（前2天成交量 > 前3天和前4天的最大值）
                # 条件3：持仓量增加信号（increase_oi函数返回True）
                if (
                    (
                        self.is_early_morning
                        or (
                            self.alert_all["POSITIONS"].get(
                                symbol, [0, 0, "BUY", "SHORT"]
                            )[3]
                            != "LONG"
                        )
                    )
                    and kline_close[-2] < kline_close[-1]
                    and max(kline_volume[-3], kline_volume[-2]) < kline_volume[-1]
                    and await self.increase_oi(
                        semaphore, symbol, "LONG", kline_close, kline_volume, dtn
                    )
                ):
                    if close_info and close_info[3] == "SHORT":
                        self.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 1
                        )
                    zy = kline_close[-1] * (1 + kline_zf)
                    zs = kline_close[-1] * (1 - kline_zf)
                    # 发送做多信号通知
                    self.send_msg(
                        f"==={symbol}做多===\n价格:{kline_close[-1]}\n止盈:{zy}\n止损:{zs}"
                    )
                    self.alert_all["OBSERVATIONS"][symbol] = [
                        kline_close[-1],
                        time.time(),
                        "SELL",
                        "LONG",
                    ]

                # 做空信号判断：需要同时满足以下条件
                # 条件1：价格连续下跌（前3天 > 前2天 > 前1天）
                # 条件2：成交量放大（前2天成交量 > 前3天和前4天的最小值）
                # 条件3：持仓量增加信号（increase_oi函数返回True）
                elif (
                    (
                        self.is_early_morning
                        or (
                            self.alert_all["POSITIONS"].get(
                                symbol, [0, 0, "SELL", "LONG"]
                            )[3]
                            != "SHORT"
                        )
                    )
                    and kline_close[-1] < kline_close[-2]
                    and await self.increase_oi(
                        semaphore, symbol, "SHORT", kline_close, kline_volume, dtn
                    )
                ):
                    if close_info and close_info[3] == "LONG":
                        self.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 1
                        )
                    zy = kline_close[-1] * (1 - kline_zf * 0.5)
                    zs = kline_close[-1] * (1 + kline_zf)
                    # 发送做空信号通知
                    self.send_msg(
                        f"==={symbol}**BD**===\n价格:{kline_close[-1]}\n止盈:{zy}\n止损:{zs}"
                    )
                    # 执行开仓操作
                    if self.open_bn_position(symbol, "SELL", "SHORT", 0.1):
                        # 记录持仓信息：[止盈价, 止损价, 平仓方向, 持仓方向]
                        self.alert_all["POSITIONS"][symbol] = [zs, zy, "BUY", "SHORT"]
        except Exception:
            # 异常处理：打印错误信息但不中断程序
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
        for p in position_risk:
            entryPrice = float(p["entryPrice"])
            if p["symbol"] not in self.alert_all["POSITIONS"]:
                if p["positionSide"] == "LONG":
                    self.alert_all["POSITIONS"][p["symbol"]] = [
                        entryPrice * 1.03,
                        entryPrice * 0.97,
                        "SELL",
                        "LONG",
                        entryPrice,
                    ]
                else:
                    self.alert_all["POSITIONS"][p["symbol"]] = [
                        entryPrice * 1.03,
                        entryPrice * 0.97,
                        "BUY",
                        "SHORT",
                        entryPrice,
                    ]
            elif len(self.alert_all["POSITIONS"][p["symbol"]]) < 5:
                self.alert_all["POSITIONS"][p["symbol"]].append(entryPrice)
            else:
                self.alert_all["POSITIONS"][p["symbol"]][-1] = entryPrice

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
        now = datetime.datetime.now()
        self.is_early_morning = now.hour == 8 and now.minute == 10
        if self.is_early_morning:
            self.send_msg(f"{market}任务开始 - {now}")

        # 重试机制：最多尝试10次获取交易对信息
        if now.minute % 15 == 0 or not self.symbols:
            for i in range(10):
                try:
                    self.get_position_risk()
                    self.get_symbols_info()
                    self.symbols = list(self.symbols_info.keys())
                    break  # 成功获取，退出重试循环
                except Exception:
                    # 获取失败，等待2秒后重试
                    traceback.print_exc()
                    await asyncio.sleep(2)
        # 创建信号量，限制最大并发数为10，避免API限制
        semaphore = asyncio.Semaphore(10)
        print(now, f"{market}任务开始 - 总交易对数量: {len(self.symbols)}", flush=True)

        success = set()  # 记录成功处理的交易对
        chunk_size = 10  # 分批处理，避免内存占用过高
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
    @staticmethod
    def get_last_trading_days(today=None, days=60):
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
            start_date = recent_trading_days.min().strftime("%Y%m%d")  # 最早日期
            end_date = recent_trading_days.max().strftime("%Y%m%d")  # 最晚日期

            # 选择第3天到第10天的交易日作为涨停股查询日期（避开最近的波动）
            zt_date = [i.strftime("%Y%m%d") for i in recent_trading_days.iloc[3:10]]

            return start_date, end_date, zt_date
        except Exception as e:
            print(f"获取交易日历失败: {str(e)}", flush=True)
            return None, None, []

    @classmethod
    def filter_stocks(cls):
        """
        筛选符合量能条件的A股股票

        功能：从涨停股池中筛选出符合低吸条件的股票
        策略：寻找有上涨动能但可能进入回调的优质股票
        返回：
            符合条件的股票代码和名称集合
        """
        # 获取交易日历信息
        start_date, end_date, zt_dates = cls.get_last_trading_days()
        selected = set()  # 存储符合条件的股票

        # 遍历近期涨停日期，获取涨停股池
        for i, zt_date in enumerate(zt_dates):
            # 获取当天涨停股票列表
            zt_df = ak.stock_zt_pool_em(date=zt_date)
            if zt_df.empty:
                print(f"没有在 {zt_date} 找到涨停股票。", flush=True)
                continue

            # 提取股票代码和名称
            stock_codes = zt_df[["代码", "名称"]].values.tolist()
            print(f"{zt_date}涨停股：{stock_codes}", flush=True)

            # 遍历涨停股票，进行技术分析
            for code in stock_codes:
                try:
                    # 获取股票历史数据（前复权）
                    hist = ak.stock_zh_a_hist(
                        symbol=code[0],
                        period="daily",
                        start_date=start_date,
                        end_date=end_date,
                        adjust="qfq",
                    )
                except Exception:
                    # 获取数据失败，跳过该股票
                    traceback.print_exc()
                    continue

                # 添加最新涨跌幅到股票信息中
                code.append(str(hist.iloc[-1]["涨跌幅"]))
                print(code, flush=True)

                # 股票筛选条件：多维度筛选优质股票
                # 条件1：数据量充足（至少60天历史数据）
                if len(hist) < 60:
                    continue

                # 条件2：当日必须上涨（涨跌幅>0）
                if hist.iloc[-1]["涨跌幅"] <= 0:
                    continue

                # 条件3：价格位置检查
                # 3a：当前价格必须高于近10天均价（确保在上升趋势中）
                # 3b：检查近期是否有价格回调（避免追高）
                if hist.iloc[-10:]["收盘"].mean() > hist.iloc[-1]["收盘"] or any(
                    hist.iloc[-9 + x : x + 1]["收盘"].mean() > hist.iloc[x]["收盘"]
                    for x in range(-2, -i - 5, -1)
                ):
                    continue

                # 条件4：成交量检查（当日成交量必须是近期最大）
                # 确保有足够的资金关注和参与
                if hist.iloc[-3:-1]["成交量"].max() > hist.iloc[-1]["成交量"]:
                    continue

                # 条件5：价格位置检查（当前价格必须在近期低点附近）
                # 避免在高位追涨，寻找回调买入机会
                if hist.iloc[: -i - 4]["收盘"].max() > hist.iloc[-i - 4]["收盘"]:
                    continue

                # 条件6：避免连续上涨（防止追高）
                # 检查近期是否有连续放量上涨的情况
                if i > 0 and any(
                    hist.iloc[x]["成交量"] > hist.iloc[x - 2 : x]["成交量"].max()
                    for x in range(-2, -i - 2, -1)
                ):
                    continue
                # 通过所有筛选条件，添加到结果集合
                selected.add("".join(code))

        return selected

    @classmethod
    def monitor_stocks(cls):
        """
        监控A股并发送通知

        功能：筛选符合条件的A股股票，并通过企业微信发送通知
        策略：低吸策略，寻找回调买入机会
        """
        # 筛选符合量能条件的股票
        filtered = cls.filter_stocks()
        print(f"符合量能条件的股票：{filtered}", flush=True)

        # 如果有符合条件的股票，发送通知
        if filtered:
            # 构建企业微信消息格式
            json_msg = {
                "msgtype": "text",
                "text": {
                    "content": f"===A{len(filtered)}低吸===\n"
                    + "\n-------\n".join(filtered)
                },
            }
            # 发送到企业微信群
            requests.post(
                url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73",
                headers={"Content-Type": "application/json"},
                json=json_msg,
                verify=False,
            )


async def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    autobn = AUTOBN.from_cfg(
        bn_api_file=os.path.join(current_dir, "bn.json"),
        alert_all_file=os.path.join(current_dir, "alert_all.json"),
        qy_key="6f2ec864-c474-4c8f-b069-1e3c35eb7d73",
    )
    """
    主函数：设置定时任务并启动调度器

    功能：配置并启动所有定时任务
    任务1：A股监控（交易时段执行）
    任务2：币安市场分析（每天8点执行）
    """
    # await autobn.rzq_market("BN")
    # return
    # 设置A股监控定时任务
    scheduler.add_job(
        AUTOA.monitor_stocks,  # 执行的函数
        "cron",  # 调度类型：按日历规则
        hour="12,14",  # 交易时段：12点和14点
        minute="52-57",  # 每小时的52-57分
        second="00",  # 整点秒数
        day_of_week="mon-fri",  # 周一至周五（交易日）
        timezone="Asia/Shanghai",  # 上海时区
        misfire_grace_time=60,  # 错过执行的宽限时间（秒）
        max_instances=1,  # 同一时间只允许1个实例运行
        coalesce=True,  # 合并错过的执行（避免积压）
        name="股票监控任务",  # 任务名称
    )

    # 设置币安市场分析定时任务
    # scheduler.add_job(
    #     autobn.rzq_market,  # 执行的函数
    #     "cron",  # 调度类型：按日历规则
    #     hour="*",  # 每小时执行
    #     minute="*",  # 每5分钟
    #     second="00",  # 整点秒数
    #     timezone="Asia/Shanghai",  # 上海时区
    #     args=("BN",),  # 传递参数
    #     misfire_grace_time=10,  # 错过执行的宽限时间（秒）
    #     max_instances=1,  # 同一时间只允许1个实例运行
    #     coalesce=True,  # 合并错过的执行（避免积压）
    #     name="币安市场分析任务",  # 任务名称
    # )

    # 启动调度器
    scheduler.start()

    # 创建一个永不触发的事件，使程序一直运行
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发（实际不会发生）


if __name__ == "__main__":
    """
    程序入口：初始化配置并启动主程序

    功能：初始化所有必要的配置和客户端，然后启动主程序
    """
    print("autoBN启动", flush=True)

    # 初始化任务调度器
    scheduler = AsyncIOScheduler()

    # 启动主程序
    asyncio.run(main())
