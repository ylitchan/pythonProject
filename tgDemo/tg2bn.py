# @Date: 2024/3/6
# @Author: ylitchan
# @Source: rdti_crawl_defense
# @Site:
import asyncio
import gc
import json
import re
import time
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
from datetime import datetime
import os
import sys

# 添加项目根目录到系统路径
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from tokenDemo.autoBN import AUTOBN


# Telegram API凭证 - 用于连接到Telegram客户端
api_id = 20214904
api_hash = "9e4d64ec1b5a77c416b4e5522ce8d325"
# 创建Telegram客户端实例
app = Client("my_account", api_id, api_hash)
last_msg = [""]


class HandleMsg:
    """
    消息处理类，用于处理来自特定Telegram频道的消息并执行相应的币安交易操作
    """

    def __init__(self):
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        bn_api_file = os.path.join(current_dir, "bn.json")
        allert_all_file = os.path.join(current_dir, "alert_all.json")
        # 初始化币安自动交易实例
        self.autobn = AUTOBN.from_cfg(
            bn_api_file=bn_api_file,
            allert_all_file=allert_all_file,
            margin_mode="CROSSED",
            qy_key="095984b1-5bc0-43ac-8037-d65a9608d120",
            leverage=5,
        )
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self.scheduler.add_job(
            self.handle_market,
            "cron",
            hour="*",
            minute="*",
            second="00",
            # next_run_time=datetime.now(),  # 启动后立即执行一次
            misfire_grace_time=10,
            max_instances=1,
            coalesce=True,
            name="跟单止损任务",
        )
        self.scheduler.add_job(
            self.send_balance,
            "cron",
            hour="08",
            minute="00",
            second="00",
            misfire_grace_time=300,
            max_instances=1,
            coalesce=True,
            name="账户信息推送",
        )

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
                # 获取持仓量历史数据（30天）
                oi = await asyncio.to_thread(
                    self.autobn.um_futures_client.open_interest_hist,
                    symbol=symbol,
                    period="15m",
                    limit=30,
                )
                # 获取当前时间并设置为最近的前一个整点时间（0,15,30,45分）
                minute = dtn.minute
                # 计算最近的前一个整点时间
                if minute < 15:
                    target_minute = 0
                elif minute < 30:
                    target_minute = 15
                elif minute < 45:
                    target_minute = 30
                else:
                    target_minute = 45
                dtn_target = dtn.replace(minute=target_minute, second=0, microsecond=0)
                if oi[-1]["timestamp"] != int(dtn_target.timestamp() * 1000):
                    return False
                sumOpenInterestValue = [
                    float(i["sumOpenInterestValue"]) for i in oi
                ]  # 持仓价值（美元）
                sumOpenInterest = [
                    float(i["sumOpenInterest"]) for i in oi
                ]  # 持仓数量（合约数）
                # 打印分析数据，便于监控和调试
                print(
                    f"{symbol} 增仓信号{max(sumOpenInterest[-3:-1])}——>{sumOpenInterest[-1]} ${max(sumOpenInterestValue[-3:-1])}——>${sumOpenInterestValue[-1]}",
                    flush=True,
                )
                if positionSide == "LONG":
                    # 做多条件检查：需要持仓量增加且多空比小于1（空头占优）
                    # 条件1：最新持仓量必须大于前3天最大值（说明有资金流入）
                    if sumOpenInterest[-1] > max(
                        sumOpenInterest[:-1]
                    ) and sumOpenInterestValue[-1] > max(sumOpenInterestValue[:-1]):
                        return True
                    else:
                        result = any(
                            (
                                kline_close[index - 1] == max(kline_close)
                                and sumOpenInterestValue[index]
                                == max(sumOpenInterestValue)
                                and kline_close[-2] > max(kline_close[-4:-2])
                                and sumOpenInterestValue[-1]
                                > max(sumOpenInterestValue[-3:-1])
                                and max(kline_volume[-3:-1]) == max(kline_volume)
                                and sumOpenInterest[-1] < sumOpenInterest[-2]
                            )
                            for index in range(-1, int(-len(kline_close) / 3) - 2, -1)
                        )
                    return None if result else False
            except Exception:
                traceback.print_exc()
                return False

    async def handle_token(self, semaphore, symbol, success, dtn):
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
            # 获取日K线数据（30天）
            kline = await self.autobn.get_kline(semaphore, symbol, "15mutc")
            kline_close = [k[4] for k in kline]  # 提取收盘价列表
            kline_volume = [k[5] for k in kline]
            kline_zf = sum(
                list(map(lambda k: abs(k[4] / k[1] - 1), kline[-8:-1]))
            ) / len(kline[-8:-1])
            success.add(symbol)  # 记录成功处理的交易对
            # 检查现有持仓是否需要平仓
            if close_info := self.autobn.alert_all["POSITIONS"].get(symbol):
                # close_info格式：[止盈价, 止损价, 平仓方向, 持仓方向]
                # 平仓条件：价格触及止损/止盈 或 减仓信号触发
                if (
                    kline_close[-1] <= close_info[1]
                    or close_info[3] == "LONG"
                    and kline_close[-1] < sum(kline_close[-7:]) / len(kline_close[-7:])
                ):
                    if close_info[3] == "LONG":
                        self.autobn.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 1
                        )
                        self.autobn.alert_all["POSITIONS"].pop(symbol)
                        self.autobn.alert_all["OBSERVATIONS"][symbol] = [
                            max(kline_close),
                            time.time(),
                            "SELL",
                            "LONG",
                        ]
                    else:
                        self.autobn.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 0.5
                        )
                        close_info[1] = kline_close[-1] * (1 - kline_zf)
                        close_info[0] = kline_close[-1] * (1 + kline_zf)
                elif kline_close[-1] >= close_info[0]:
                    if close_info[3] == "SHORT":
                        self.autobn.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 1
                        )
                        self.autobn.alert_all["POSITIONS"].pop(symbol)
                    else:
                        self.autobn.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 0.5
                        )
                        close_info[0] = kline_close[-1] * (1 + kline_zf)
                        close_info[1] = kline_close[-1] * (1 - kline_zf)
                elif dtn.minute % 5 == 0:
                    if close_info[3] == "SHORT" and kline_close[-1] < close_info[-1]:
                        self.autobn.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 0.5
                        )
                    elif close_info[3] == "LONG" and kline_close[-1] > close_info[-1]:
                        self.autobn.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 0.5
                        )
                        self.autobn.alert_all["OBSERVATIONS"][symbol] = [
                            max(kline_close),
                            time.time(),
                            "SELL",
                            "LONG",
                        ]
            elif open_info := self.autobn.alert_all["OBSERVATIONS"].get(symbol):
                if time.time() - open_info[1] > 15 * 30 * 60:
                    self.autobn.alert_all["OBSERVATIONS"].pop(symbol)
                elif (
                    open_info[3] == "LONG"
                    and kline_close[-2] > open_info[0]
                    and all(
                        kline_close[x]
                        >= sum(kline_close[x - 6 : x + 1])
                        / len(kline_close[x - 6 : x + 1])
                        for x in range(-2, -4, -1)
                    )
                    and max(kline_volume[-3], kline_volume[-4]) < kline_volume[-2]
                    and await self.autobn.decrease_oi(
                        semaphore,
                        symbol,
                        open_info[3],
                        kline_close,
                        kline_volume,
                        dtn,
                        open_info[0],
                    )
                ):
                    zy = kline_close[-1] * (1 + kline_zf)
                    zs = kline_close[-1] * (1 - kline_zf)
                    self.autobn.send_msg(
                        f"==={symbol}**BZ**===\n价格:{kline_close[-1]}\n止盈:{zy}\n止损:{zs}"
                    )
                    if self.autobn.open_bn_position(symbol, "BUY", "LONG", 0.03):
                        self.autobn.alert_all["POSITIONS"][symbol] = [
                            zy,
                            zs,
                            "SELL",
                            "LONG",
                        ]
                        self.autobn.alert_all["OBSERVATIONS"].pop(symbol)
            if dtn.minute % 3 == 0:
                signal = await self.increase_oi(
                    semaphore, symbol, "LONG", kline_close, kline_volume, dtn
                )
                if (
                    signal
                    and self.autobn.alert_all["POSITIONS"].get(
                        symbol, [0, 0, "BUY", "SHORT"]
                    )[3]
                    != "LONG"
                    and self.autobn.alert_all["OBSERVATIONS"].get(
                        symbol, [0, 0, "BUY", "SHORT"]
                    )[3]
                    != "LONG"
                    and kline_close[-2] > max(kline_close[:-2])
                    and kline_volume[-2] > max(kline_volume[:-2])
                    and sum(kline_volume[: -int(len(kline) / 2)])
                    / len(kline_volume[: -int(len(kline) / 2)])
                    * 9
                    < kline_volume[-2]
                    and all(
                        kline_volume[x] > kline_volume[x - 2] for x in range(-2, -6, -2)
                    )
                    and all(
                        kline_close[x]
                        >= sum(kline_close[x - 6 : x + 1])
                        / len(kline_close[x - 6 : x + 1])
                        for x in range(-2, -7, -1)
                    )
                ):
                    zy = kline_close[-1] * (1 + kline_zf)
                    zs = kline_close[-1] * (1 - kline_zf)
                    if close_info and close_info[3] == "SHORT":
                        self.autobn.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 1
                        )
                    self.autobn.send_msg(
                        f"==={symbol}做多===\n价格:{kline_close[-1]}\n止盈:{zy}\n止损:{zs}"
                    )
                    if self.autobn.open_bn_position(symbol, "BUY", "LONG", 0.03):
                        self.autobn.alert_all["POSITIONS"][symbol] = [
                            zy,
                            zs,
                            "SELL",
                            "LONG",
                        ]
                elif (
                    signal is None
                    and self.autobn.alert_all["POSITIONS"].get(
                        symbol, [0, 0, "SELL", "LONG"]
                    )[3]
                    != "SHORT"
                    and self.autobn.alert_all["OBSERVATIONS"].get(
                        symbol, [0, 0, "SELL", "LONG"]
                    )[3]
                    != "SHORT"
                ):
                    zy = kline_close[-1] * (1 - kline_zf)  # 止盈价
                    zs = kline_close[-1] * (1 + kline_zf)  # 止损价
                    if close_info and close_info[3] == "LONG":
                        self.close_bn_position(
                            symbol, close_info[2], close_info[3], kline_close[-1], 1
                        )
                    self.autobn.send_msg(
                        f"==={symbol}做空===\n价格:{kline_close[-1]}\n止盈:{zy}\n止损:{zs}"
                    )
                    if self.autobn.open_bn_position(symbol, "SELL", "SHORT", 0.03):
                        self.autobn.alert_all["POSITIONS"][symbol] = [
                            zs,
                            zy,
                            "BUY",
                            "SHORT",
                        ]
        except Exception:
            # 异常处理：打印错误信息但不中断程序
            traceback.print_exc()
            return

    async def handle_market(self):
        """
        市场分析主函数：获取交易对信息并批量处理

        功能：这是整个交易系统的入口函数，负责：
        1. 获取所有可交易的USDT交易对
        2. 清理无效的持仓记录
        3. 批量分析所有交易对
        4. 保存分析结果
        """
        now = datetime.now()
        symbols = []

        # 重试机制：最多尝试10次获取交易对信息
        for i in range(10):
            try:
                self.autobn.get_position_risk()
                self.autobn.get_symbols_info()
                symbols = list(self.autobn.symbols_info.keys())
                break  # 成功获取，退出重试循环
            except Exception:
                # 获取失败，等待2秒后重试
                traceback.print_exc()
                await asyncio.sleep(2)
        # 创建信号量，限制最大并发数为10，避免API限制
        semaphore = asyncio.Semaphore(10)
        print(now, f"跟单止损任务开始 - 持仓交易对数量: {len(symbols)}", flush=True)

        success = set()  # 记录成功处理的交易对
        chunk_size = 10  # 分批处理，避免内存占用过高

        # 分批处理所有交易对
        for i in range(0, len(symbols), chunk_size):
            symbol_chunk = symbols[i : i + chunk_size]  # 当前批次的交易对
            # 创建异步任务列表
            tasks = [
                self.handle_token(semaphore, symbol, success, now)
                for symbol in symbol_chunk
            ]
            # 等待当前批次所有任务完成
            await asyncio.gather(*tasks)
            gc.collect()  # 垃圾回收，释放内存
        # 打印任务完成信息
        print(
            datetime.now(),
            f"跟单止损任务结束 - 持仓交易对数量: {len(success)}",
            self.autobn.alert_all,
            flush=True,
        )
        # 保存分析结果到文件
        current_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(current_dir, "alert_all.json"), "w") as f:
            json.dump(self.autobn.alert_all, f, ensure_ascii=False, indent=4)

    async def send_balance(self, account_data=None):
        """
        发送账户余额和持仓信息到消息通道

        Args:
            account_data (dict): 包含账户信息的字典
        """
        # 获取账户可用余额
        if account_data is None:
            account_data = self.autobn.um_futures_client.account()
        balance = account_data["totalWalletBalance"]
        position_risk = []
        for p in account_data["positions"]:
            position_risk.append(
                f"==={p['symbol']}===\n开仓价格:{float(p['notional']) / float(p['positionAmt'])} USDT\n持仓方向:{p['positionSide']}\n名义价值:{p['notional']} USDT\n持仓收益:{p['unrealizedProfit']} USDT"
            )
        position_risk = "\n\n".join(position_risk)
        self.autobn.send_msg(f"账户余额:\n{balance} USDT\n持仓信息:\n{position_risk}")

    async def handle_msg(self, message):
        """
        处理【熬鹰资本聪明钱】频道的消息

        Args:
            message: Telegram消息对象
        """
        print(message, flush=True)
        # 检查消息时间是否为当前时间（精确到分钟）
        if message.date.replace(second=0) == datetime.now().replace(
            second=0, microsecond=0
        ):
            text = message.text or ""
            # 将消息转发到通知通道
            self.autobn.send_msg(text)
            # 处理特定频道的消息
            if "【熬鹰资本聪明钱】" in text:
                # 提取交易操作类型（开仓/加仓/减仓/平仓）
                side = re.findall("开仓|加仓|减仓|平仓", text)[0]
                # 提取交易对符号
                symbol = re.findall("【币种】.*?(\w+USDT).*?\n", text)[0]
                # 提取开仓价格
                price = float(re.findall("【开仓价】.*?(\d+(?:\.\d+)?).*?\n", text)[0])
                # 提取持仓方向
                positionSide = re.findall("【方向】(.*?)\n", text)[0]
                # 发送交易提醒
                self.autobn.send_msg(f"==={symbol}{side}===\n开仓价:{price}")
                # 根据方向和操作类型执行相应的交易操作
                if "空" in positionSide:
                    positionSide = "SHORT"
                    if side == "减仓":
                        self.autobn.close_bn_position(
                            symbol, "BUY", positionSide, price, close_ratio=0.5
                        )
                    elif side == "平仓":
                        self.autobn.close_bn_position(
                            symbol, "BUY", positionSide, price, close_ratio=1
                        )
                    elif side == "加仓":
                        self.autobn.open_bn_position(symbol, "SELL", positionSide)
                    elif side == "开仓":
                        self.autobn.open_bn_position(symbol, "SELL", positionSide)
                elif "多" in positionSide:
                    positionSide = "LONG"
                    if side == "减仓":
                        self.autobn.close_bn_position(
                            symbol, "SELL", positionSide, price, close_ratio=0.5
                        )
                    elif side == "平仓":
                        self.autobn.close_bn_position(
                            symbol, "SELL", positionSide, price, close_ratio=1
                        )
                    elif side == "加仓":
                        self.autobn.open_bn_position(symbol, "BUY", positionSide)
                    elif side == "开仓":
                        self.autobn.open_bn_position(symbol, "BUY", positionSide)

    async def handle_msg2(self, message):
        """
        处理CM AI SIGNAL频道的消息

        Args:
            message: Telegram消息对象
        """
        text = message.text or ""
        print(datetime.now(), text, flush=True)
        # 获取聊天标题和ID
        title = message.chat.title if message.chat else ""
        channel_id = message.chat.id if message.chat else 0
        # 处理指定频道的消息
        if title in ["方程式新闻 BWEnews"] or channel_id == -1001279597711:
            # 将消息转发到通知通道
            self.autobn.send_msg(text)
            return
            texts = text.split("\n")
            # 提取交易信号类型
            side = re.findall("涨|跌|开仓|加仓|减仓|平仓", texts[0])[0]
            # 确定持仓方向
            positionSide = "LONG" if side == "涨" else "SHORT"
            # 提取交易对符号
            symbol = re.findall(".*?(\w+USDT).*?", texts[0])[0]

            # 处理猎龙忍者信号
            if re.search("猎龙忍者|资金雷达", texts[0]):
                price = float(re.findall("价格.*?(\d+(?:\.\d+)?).*?", texts[3])[0])
                side = "BUY" if side == "涨" else "SELL"
                self.autobn.get_symbols_info()
                # 执行开仓操作并发送账户信息
                if account_data := self.autobn.open_bn_position(
                    symbol, side, positionSide, open_ratio=0.015
                ):
                    print(account_data, flush=True)
                    # 记录持仓信息：[止盈价, 止损价, 平仓方向, 持仓方向]
                    self.autobn.alert_all["POSITIONS"][symbol] = [
                        price * 1.05,
                        price * 0.95,
                        "BUY" if side == "SELL" else "SELL",
                        positionSide,
                    ]

            # 处理跟踪止损设置提醒
            elif "跟踪止损设置提醒" in texts[0]:
                price = float(re.findall("价格.*?(\d+(?:\.\d+)?).*?", texts[3])[0])
                side = "SELL" if side == "涨" else "BUY"
                if symbol in self.autobn.alert_all["POSITIONS"]:
                    self.autobn.alert_all["POSITIONS"][symbol][0] = price * 1.04
                    self.autobn.alert_all["POSITIONS"][symbol][1] = price * 0.96
                # 执行减仓操作（50%）
                self.autobn.close_bn_position(
                    symbol, side, positionSide, price, close_ratio=0.7
                )

            # 处理跟踪结束信号
            elif "跟踪结束" in texts[0]:
                price = float(re.findall("价格.*?(\d+(?:\.\d+)?).*?", texts[4])[0])
                side = "SELL" if side == "涨" else "BUY"
                # 执行平仓操作（100%）
                self.autobn.close_bn_position(
                    symbol, side, positionSide, price, close_ratio=1
                )


# @app.on_raw_update()
# async def handle_raw(_, update, users, chats):
#     print(update, flush=True)
#     if hasattr(update, 'message'):
#         handle_msg2(update.message)
#     async for i in _.get_chat_history(-1002651333064, limit=1):
#         print(i, flush=True)
#         if i.text != last_msg[-1]:
#         last_msg[-1] = i.text
#         handle_msg(i)


# 处理被编辑的消息
@app.on_edited_message()
async def on_edit(client, message):
    """
    当消息被编辑时触发的回调函数

    Args:
        client: Telegram客户端实例
        message: 被编辑的Telegram消息对象
    """
    print("on_edited_message", flush=True)
    await handle_msg.handle_msg2(message)


# 处理新消息
@app.on_message()
async def raw(client, message):
    """
    当收到新消息时触发的回调函数

    Args:
        client: Telegram客户端实例
        message: 新的Telegram消息对象
    """
    print("on_message", flush=True)
    if handle_msg.scheduler.state == 0:
        handle_msg.scheduler.start()
    await handle_msg.handle_msg2(message)


async def main():
    handle_msg.scheduler.start()
    # 创建一个永不触发的事件，使程序一直运行
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发（实际不会发生）


# 程序入口点
if __name__ == "__main__":
    # 初始化消息处理器
    handle_msg = HandleMsg()
    # 启动Telegram客户端
    # app.run()
    asyncio.run(main())
