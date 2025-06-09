# ==================================================================================================
# 文件名: autoBN.py
# 功能描述: Binance交易自动化工具，提供以下功能：
#   1. 量能分析和交易信号生成
#   2. 自动交易执行（做多、做空）
#   3. 账户健康度监控
#   4. 股票市场监控与筛选
#   5. 企业微信消息通知
# 作者: ylitchan
# 创建日期: 2024
# 最后修改: 2025-05-30
# ==================================================================================================

import asyncio
import datetime
import gc
import json
import traceback
from decimal import Decimal, ROUND_DOWN
from itertools import pairwise

from binance.um_futures import UMFutures
import akshare as ak
import pandas as pd
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from binance.spot import Spot
from jsonpath_ng import parse


def send_msg(msg):
    """
    发送消息到企业微信群聊

    :param msg: 要发送的消息内容
    :return: None
    """
    try:
        # 记录当前时间和消息内容
        current_time = datetime.datetime.now()
        print(f"{current_time} - 发送消息: {msg}")

        # 构建企业微信消息格式
        json_msg = {
            "msgtype": "text",
            "text": {'content': msg}
        }

        # 发送POST请求到企业微信API
        response = session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
            json=json_msg)

        # 检查响应状态（可选）
        if response.status_code != 200:
            print(f"消息发送失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"消息发送异常: {str(e)}")
        # 记录异常但不中断程序


def trade(symbol, symbols_info, slot):
    """
    执行交易操作，包括买入和卖出订单的创建

    :param symbol: 交易对符号
    :param symbols_info: 交易对信息字典
    :param slot: 仓位比例
    :return: 若交易成功返回交易对符号，否则返回 None
    """
    try:
        # 检查可用USDT余额
        usdt_assets = spotBN.user_asset(asset='USDT')
        if not usdt_assets:  # 检查是否有USDT资产数据
            send_msg(f'无法获取USDT资产信息')
            return None

        usdt_free = float(usdt_assets[0]['free'])

        # 检查最小交易额
        if usdt_free < 6:
            send_msg(f'USDT余额不足: {usdt_free}')
            return None

        # 计算实际交易额
        usdt_slot = usdt_free * slot
        if usdt_slot >= 6:
            usdt_free = usdt_slot
        else:
            send_msg(f'交易额太小: {usdt_slot}')
            return None

        # 获取交易对配置信息
        if symbol not in symbols_info:
            send_msg(f'找不到交易对信息: {symbol}')
            return None

        symbol_info = symbols_info.get(symbol)
        quotePrecision = symbol_info.get('quotePrecision')

        # 准备订单参数
        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quoteOrderQty": round(usdt_free, quotePrecision)
        }

        # 发送订单
        order_result = spotBN.new_order(**params)

        # 记录交易结果
        executed_qty = order_result.get('executedQty', '未知')
        executed_price = order_result.get('price', '市价')
        msg = f'{symbol}成功交易，交易仓位:{slot}，数量:{executed_qty}，价格:{executed_price}'
        send_msg(msg)

        return symbol
    except Exception as e:
        error_msg = f'交易{symbol}失败: {str(e)}'
        send_msg(error_msg)
        traceback.print_exc()
        return None


def calculate_health_bn(notional) -> int:
    """
    计算Binance账户的健康度（健康百分比）

    该函数计算账户的风险水平，用百分比表示。计算方法为：
    健康度 = (1 - 维持保证金总额/账户总余额) * 100%

    :param notional: 新增头寸的名义价值，用于计算额外需要的维持保证金
    :return: 账户健康度，范围为0-100的整数，100表示最健康，0表示已爆仓
    """
    account_data = um_futures_client.account()
    total_balance = float(account_data['totalMarginBalance'])  # 账户总余额
    position_data = um_futures_client.get_position_risk()
    total_maintenance_margin = 0.0  # 维持保证金总额
    for position in position_data:
        if float(position['positionAmt']) != 0:  # 只考虑有持仓的头寸
            maintenance_margin = float(position['maintMargin'])  # 当前头寸维持保证金
            total_maintenance_margin += maintenance_margin
    total_maintenance_margin += notional * 0.004  # 新增头寸所需维持保证金（假设维持保证金率为0.4%）
    if total_maintenance_margin == 0 and total_balance >= 0:
        return 100  # 无持仓且余额为正，健康度为100%
    elif total_balance <= 0:
        return 0  # 余额为负，已爆仓
    else:
        return round(
            min(100, max(0, (1 - total_maintenance_margin / total_balance) * 100))
        )


def open_bn_position(symbol, symbols_info, side, positionSide):
    """
    在Binance合约市场开仓做空

    根据账户可用余额和杠杆倍数计算开仓数量，并执行做空开仓操作。
    会检查账户健康度确保开仓后不会导致风险过高。

    :param symbol: 交易对符号，如'BTCUSDT'
    :param symbols_info: 交易对信息字典，包含精度等信息
    :return: 成功开仓返回交易对符号，失败返回None
    """
    try:
        # 获取账户可用余额
        account_data = um_futures_client.account()
        balance = float(account_data['availableBalance'])

        # 检查余额是否足够
        if balance <= 0:
            send_msg(f'{symbol} 开仓失败：可用余额为零')
            return None

        # 获取当前标记价格
        mark_price_data = um_futures_client.mark_price(symbol)
        if not mark_price_data:
            send_msg(f'{symbol} 开仓失败：无法获取标记价格')
            return None

        markPrice = float(mark_price_data['markPrice'])

        # 检查交易对配置信息
        if symbol not in symbols_info:
            send_msg(f'{symbol} 开仓失败：找不到交易对信息')
            return None

        # 计算可用资金的80%作为最大可用金额（保留部分资金作为缓冲）
        safe_balance = balance * 0.2

        # 根据杠杆计算交易数量
        amount_raw = safe_balance * leverage / markPrice

        # 按照交易对精度要求四舍五入（向下取整，避免超出可用余额）
        amount = float(
            Decimal(str(amount_raw)).quantize(symbols_info.get(symbol)['quantityPrecision'], rounding=ROUND_DOWN))

        # 计算名义价值
        notional = amount * markPrice

        # 检查最小交易额
        if notional < 6:
            send_msg(f'{symbol} 开仓失败：交易额 {notional} 低于最小要求 6 USDT')
            return None

        # 检查开仓后的账户健康度
        account_health = calculate_health_bn(notional)
        if account_health < health4open:
            send_msg(f'{symbol} 开仓失败：预计健康度 {account_health}% 低于要求 {health4open}%')
            return None

        # 设置杠杆
        leverage_result = um_futures_client.change_leverage(symbol=symbol, leverage=leverage)
        actual_leverage = leverage_result.get('leverage', leverage)

        # 下市价单做空
        tx = um_futures_client.new_order(
            symbol=symbol,
            side='SELL',
            type="MARKET",
            quantity=amount,
            positionSide="SHORT",
        )

        # 发送成功通知
        msg = f'{symbol}成功{side}，杠杆:{actual_leverage}x，交易数量:{tx.get("origQty", 0)}，标记价格:{markPrice}'
        send_msg(msg)
        return symbol
    except Exception as e:
        error_msg = f'{symbol} 开仓失败：{str(e)}'
        send_msg(error_msg)
        traceback.print_exc()
        return None


async def get_kline(semaphore, symbol, t: str):
    """
    异步获取指定交易对的 K 线数据

    :param semaphore: 异步信号量，用于控制并发数量
    :param symbol: 交易对符号，例如 "BTCUSDT"
    :param t: K 线时间周期，如 "1Dutc"（1天UTC时间）、"4h"（4小时）等
    :return: K 线数据列表，元素为浮点数列表，每个子列表包含[开盘时间, 开盘价, 最高价, 最低价, 收盘价, 成交量, ...]等信息
    """
    async with semaphore:
        # 提取时间周期前缀（如 1d, 4h 等）并转小写
        interval = t[:2].lower()
        # 使用 asyncio.to_thread 在线程池中执行阻塞的 API 调用
        kline = await asyncio.to_thread(spotBN.klines, symbol=symbol, interval=interval, limit=20)
        # 一次性将所有数据转换为浮点数
        return [list(map(float, sublist)) for sublist in kline]


def calculate_ema_pandas(prices, period=None):
    """
    使用 pandas 计算指数移动平均线 (EMA)

    EMA是一种赋予近期数据更高权重的移动平均线，计算公式为：
    EMA(today) = Price(today) * k + EMA(yesterday) * (1 – k)
    其中 k = 2/(period + 1)

    :param prices: 价格数据列表，包含历史价格数据
    :param period: 计算 EMA 的周期，默认为价格数据列表的长度。较小的周期对最新数据更敏感
    :return: 最后一个 EMA 值，即最新的 EMA 计算结果
    """
    # 如果未提供周期，则使用全部数据长度
    if not period:
        period = len(prices)
    # 直接使用 pandas Series 创建数据并计算 EMA
    # ewm: 指数加权移动，span参数设置为period使其等价于交易软件中的EMA
    # adjust=False确保使用标准EMA计算方法
    return pd.Series(prices).ewm(span=period, adjust=False).mean().iloc[-1]


async def rzq_token(semaphore, symbol, success, symbols_info):
    """
    异步分析指定交易对的 K 线数据，筛选符合交易条件的交易对并执行交易

    该函数通过分析K线数据的价格变动和成交量模式，识别做多和做空信号：
    - 做多信号：当日涨幅为近10天最大且成交量为近10天最高
    - 做空信号：当日为阴线，前一日涨幅为近10天最大且成交量为前10天的2倍，并且前日上影线足够长

    :param semaphore: 异步信号量，用于控制并发请求数量
    :param symbol: 交易对符号，如 "BTCUSDT"
    :param alert: 存储符合条件的交易对信息的字典
    :param success: 存储成功获取 K 线数据的交易对集合
    :param symbols_info: 交易对信息字典，包含交易精度等信息
    :return: 若不符合条件则返回 None，否则返回符合条件的交易对信息字典
    """
    try:
        # 检查是否已在交易中，避免重复交易
        if symbol in alert_all['POSITIONS']:
            return
        # 获取日K线数据
        kline = await get_kline(semaphore, symbol, "1Dutc")
        success.add(symbol)
        # 计算涨跌幅：收盘价/开盘价-1
        kline_zf = list(map(lambda k: k[4] / k[1] - 1, kline))
        if len(kline) < 20:  # 数据不足，跳过
            return
        # 提取 K 线数据中的各项指标
        kline_close = [k[4] for k in kline]  # 收盘价列表
        kline_vol = [k[5] for k in kline]  # 成交量列表

        # 计算关键指标
        recent_zf_max = max([abs(k) for k in kline_zf[-10:-1]])  # 近10天最大涨跌幅（绝对值）
        recent_vol_max = max(kline_vol[-10:-1])  # 近10天最大成交量

        # 做多条件：当日涨幅为近10天最大且成交量为近10天最高
        if (1.2 * recent_zf_max >= kline_zf[-1] >= recent_zf_max and kline_vol[-1] >= recent_vol_max / 2
                and (kline[-1][2] - kline_close[-1]) / kline[-1][1] < kline_zf[-1] / 2):
            send_msg(f'==={symbol}做多===\n价格:{kline_close[-1]}\n涨幅:{kline_zf[-1]:.2%}')
            alert_all['POSITIONS'].append(symbol)
            open_bn_position(symbol, symbols_info, 'BUY', 'LONG')
            trade(symbol=symbol, symbols_info=symbols_info, slot=0.2)

        # 做空条件：
        # 1. 当日为阴线(涨跌幅为负)
        # 2. 前一日涨跌幅为近10天最大
        # 3. 前一日成交量为前10天的2倍以上
        # 4. 前一日上影线足够长（至少为涨幅的一半）
        elif (kline_zf[-1] < 0 and  # 当日为阴线
              kline_zf[-2] >= max([abs(k) for k in kline_zf[-11:-1]]) and  # 前一日涨幅最大
              kline_vol[-2] >= 2 * max(kline_vol[-11:-2]) and  # 前一日成交量是前10天的2倍以上
              (kline[-2][2] - kline_close[-2]) / kline[-2][1] >= kline_zf[-2] / 2):  # 上影线足够长
            send_msg(f'==={symbol}做空===\n价格:{kline_close[-1]}\n涨幅:{kline_zf[-1]:.2%}')
            alert_all['POSITIONS'].append(symbol)
            open_bn_position(symbol, symbols_info, 'SELL', 'SHORT')
    except:
        traceback.print_exc()
        return


async def rzq_market(market):
    """
    异步执行市场分析任务，筛选符合条件的交易对并进行交易操作，最后记录结果并发送通知

    该函数是交易逻辑的主要入口，执行以下步骤：
    1. 获取所有符合条件的交易对
    2. 对每个交易对并发执行技术分析（调用rzq_token函数）
    3. 对符合条件的交易对执行交易策略
    4. 汇总交易结果并发送通知
    5. 保存分析数据

    每天早上8点会清空历史数据，重新开始分析和交易。

    :param market: 市场名称，如 'BN'（币安）
    """
    now = datetime.datetime.now()
    symbols = []
    POSITIONS = alert_all.get("POSITIONS", {})
    # 每天早上8点重置数据
    if now.hour == 8 and now.minute < 2:
        POSITIONS.clear()
    for i in range(10):
        try:
            sp = {i['symbol']: Decimal('1') if i['quantityPrecision'] == 0 else Decimal(
                f'0.{"1" * i["quantityPrecision"]}') for i in um_futures_client.exchange_info()['symbols']}
            exchange_info = await asyncio.to_thread(spotBN.exchange_info)
            symbols_info = {symbol['symbol']: {
                'quotePrecision': symbol['quotePrecision'],
                'quantityPrecision': sp.get(symbol['symbol'], Decimal('1'))
            }
                for symbol in exchange_info['symbols'] if
                symbol['symbol'] not in POSITIONS and 'USDT' in symbol['quoteAsset'] and 'TRADING' in
                symbol[
                    'status']}
            symbols = list(symbols_info.keys())
            break
        except:
            traceback.print_exc()
            await asyncio.sleep(2)
    # 创建并发控制信号量（限制最大并发数为10）
    semaphore = asyncio.Semaphore(10)
    print(now, f'{market}任务开始 - 总交易对数量: {len(symbols)}')

    # 初始化数据收集容器
    success = set()  # 成功处理的交易对

    # 创建并发任务
    chunk_size = 50  # 每批处理的交易对数量
    for i in range(0, len(symbols), chunk_size):
        # 分批处理以避免内存占用过高
        symbol_chunk = symbols[i:i + chunk_size]
        tasks = [rzq_token(semaphore, symbol, success, symbols_info) for symbol in symbol_chunk]
        # 等待当前批次完成
        await asyncio.gather(*tasks)
        # 进行垃圾回收以释放内存
        gc.collect()
    print(datetime.datetime.now(), f'{market}任务结束 - 总交易对数量: {len(success)}')


def get_last_trading_days(today=None, days=60):
    """
    获取最近的交易日信息，用于数据分析和历史回测

    该函数从新浪财经接口获取A股交易日历，然后计算：
    1. 指定日期前的最近n个交易日区间（起始日和结束日）
    2. 近期涨停股需要查询的日期列表（近7个交易日，但略过最近3天）

    :param today: 指定日期，默认为当前日期
    :param days: 获取最近交易日的天数，默认为 60 天
    :return: 三元组 (start_date, end_date, zt_date)
        - start_date: 查询区间起始日期，格式'YYYYMMDD'
        - end_date: 查询区间结束日期，格式'YYYYMMDD'
        - zt_date: 需要查询涨停股的日期列表，格式['YYYYMMDD', ...]
    """
    # 设置默认日期为今天
    if not today:
        today = datetime.datetime.today()

    try:
        # 从新浪获取交易日历
        trade_dates = ak.tool_trade_date_hist_sina()

        # 转换为日期时间格式
        trade_dates = pd.to_datetime(trade_dates["trade_date"])

        # 过滤出不晚于指定日期的交易日
        valid_dates = trade_dates[trade_dates <= today]

        # 如果没有有效日期，返回空结果
        if valid_dates.empty:
            print(f"警告: 未找到 {today} 之前的交易日")
            return None, None, []

        # 获取指定日期前的最近n个交易日，按时间降序排列
        recent_trading_days = valid_dates.sort_values(ascending=False).iloc[:days]

        # 计算查询区间起始日期和结束日期（时间上最早和最晚的日期）
        start_date = recent_trading_days.min().strftime("%Y%m%d")
        end_date = recent_trading_days.max().strftime("%Y%m%d")

        # 选择第3天到第10天的交易日作为涨停股查询日期（避开最近的波动）
        # 注意：iloc[3:10]表示从第4个元素到第10个元素（索引从0开始）
        zt_date = [i.strftime("%Y%m%d") for i in recent_trading_days.iloc[3:10]]

        return start_date, end_date, zt_date
    except Exception as e:
        print(f"获取交易日历失败: {str(e)}")
        # 发生异常时返回空结果
        return None, None, []


def filter_stocks():
    """
    筛选符合量能条件的A股股票

    该函数筛选满足以下条件的股票：
    1. 在近期涨停池中出现
    2. 有至少60天的交易数据
    3. 近两天不能有下跌
    4. 当前价格高于近10天均价
    5. 当日成交量大于前几天最大成交量
    6. 当日价格处于近期低点
    7. 不能有连续上涨的情况

    这些条件筛选出有较强上涨动能且可能进入回调的优质股票，适合低吸策略。

    :return: 符合条件的股票代码和名称集合
    """
    # 获取交易日信息
    start_date, end_date, zt_dates = get_last_trading_days()
    selected = set()

    # 遍历近期涨停日期
    for i, zt_date in enumerate(zt_dates):
        # 获取当天涨停股池
        zt_df = ak.stock_zt_pool_em(date=zt_date)
        if zt_df.empty:
            print(f"没有在 {zt_date} 找到涨停股票。")
            continue
        # 提取股票代码和名称
        stock_codes = zt_df[['代码', '名称']].values.tolist()
        print(f"{zt_date}涨停股：{stock_codes}")

        # 遍历涨停股票进行筛选
        for code in stock_codes:
            try:
                # 获取股票历史数据
                hist = ak.stock_zh_a_hist(symbol=code[0], period="daily", start_date=start_date, end_date=end_date,
                                          adjust="qfq")
            except:
                traceback.print_exc()
                continue

            code.append(str(hist.iloc[-1]['涨跌幅']))  # 添加最新涨跌幅
            print(code)

            # 分别检查每个筛选条件
            if len(hist) < 60:  # 数据量不足60天
                continue

            # 近两天有下跌
            if hist.iloc[-2:]['涨跌幅'].min() <= 0:
                continue

            # 当前价格低于10天均价
            if hist.iloc[-10:]['收盘'].mean() > hist.iloc[-1]['收盘']:
                continue

            # 当日成交量不是最大
            if hist.iloc[max(-3, -i - 2):-1]['成交量'].max() > hist.iloc[-1]['成交量']:
                continue

            # 不在近期低点
            if hist.iloc[:-i - 4]['收盘'].max() > hist.iloc[-i - 4]['收盘']:
                continue

            # 有连续上涨（任意两天都为正涨幅）
            if any(x > 0 and y > 0 for x, y in pairwise(hist.iloc[-i - 3:-1]['涨跌幅'].tolist())):
                continue

            # 添加符合条件的股票
            selected.add(''.join(code))

    return selected


def monitor_stocks():
    """
    实时监控符合量能条件的股票，并通过企业微信发送通知

    该函数调用filter_stocks获取符合低吸条件的股票，然后将结果通过企业微信机器人
    发送到指定群聊，便于交易员实时跟踪A股市场机会。

    通知格式：
    ===A[股票数量]低吸===
    [股票代码+名称+涨跌幅1]
    -------
    [股票代码+名称+涨跌幅2]
    ...
    """
    # 获取符合条件的股票列表
    filtered = filter_stocks()
    print(f"符合量能条件的股票：{filtered}")

    # 如果有符合条件的股票，发送通知
    if filtered:
        json_msg = {
            "msgtype": "text",
            "text": {'content': f'===A{len(filtered)}低吸===\n' + '\n-------\n'.join(filtered)}
        }
        # 发送到企业微信群
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
            json=json_msg)


async def main():
    """
    主函数，启动所有监控和交易任务

    主要功能：
    1. 立即执行一次股票监控和币安市场分析
    2. 设置定时任务：
       - 每个工作日（周一至周五）的12:52-12:57和14:52-14:57执行股票监控
       - 每分钟执行一次币安市场分析
    3. 启动调度器并保持程序运行

    该函数是程序的入口点，启动后会一直运行直到被手动终止。
    """
    # 立即执行一次股票监控
    monitor_stocks()
    # 立即执行一次币安市场分析
    await rzq_market('BN')

    # 设置股票监控定时任务 - 在交易时段执行
    scheduler.add_job(
        monitor_stocks,  # 执行的函数
        'cron',  # 调度类型：按日历规则
        hour='12,14',  # 每天12点和14点
        minute='52-57',  # 每小时的52-57分
        second='00',  # 整点秒数
        day_of_week='mon-fri',  # 周一至周五（交易日）
        timezone='Asia/Shanghai',  # 上海时区
        misfire_grace_time=60,  # 错过执行的宽限时间（秒）
        name='股票监控任务'  # 任务名称（便于日志识别）
    )

    # 设置币安市场分析定时任务 - 每分钟执行
    scheduler.add_job(
        rzq_market,  # 执行的函数
        'cron',  # 调度类型：按日历规则
        hour='08-20',  # 每天8点和20点
        minute='01-59/1',  # 每1分钟
        second='00',  # 整点秒数
        timezone='Asia/Shanghai',  # 上海时区
        args=('BN',),  # 传递参数
        misfire_grace_time=30,  # 错过执行的宽限时间（秒）
        coalesce=True,  # 合并错过的执行（避免积压）
        name='币安市场分析任务'  # 任务名称（便于日志识别）
    )

    # 启动调度器
    scheduler.start()

    # 创建一个永不触发的事件，使程序一直运行
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发（实际不会发生）


if __name__ == "__main__":
    leverage = 2
    health4open = 80
    session = requests.Session()
    session.verify = False
    session.headers = {'Content-Type': 'application/json'}
    scheduler = AsyncIOScheduler()
    with open('bn.json', 'r') as f:
        bn_api = json.load(f)
    spotBN = Spot(api_key=bn_api.get('api_key'), api_secret=bn_api.get('api_secret'))
    um_futures_client = UMFutures(key=bn_api.get('api_key'), secret=bn_api.get('api_secret'))
    alert_all = {'POSITIONS': []}
    asyncio.run(main())
