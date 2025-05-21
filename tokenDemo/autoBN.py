# 导入异步编程相关模块，用于处理异步任务
import asyncio
# 导入日期时间模块，用于获取和处理日期时间信息
import datetime
# 导入垃圾回收模块，用于手动触发垃圾回收
import gc
# 导入 JSON 处理模块，用于读写 JSON 数据
import json
# 导入时间模块，用于实现时间延迟等操作
import time
# 导入异常堆栈跟踪模块，用于打印异常详细信息
import traceback
# 从 decimal 模块导入 Decimal 类和 ROUND_DOWN 常量，用于高精度十进制运算和向下取整
from decimal import Decimal, ROUND_DOWN
from itertools import pairwise

# 导入 akshare 库，用于获取金融数据
import akshare as ak
# 导入 pandas 库，用于数据处理和分析
import pandas as pd
# 导入 requests 库，用于发送 HTTP 请求
import requests
# 从 apscheduler 库的 schedulers.asyncio 模块导入 AsyncIOScheduler 类，用于异步任务调度
from apscheduler.schedulers.asyncio import AsyncIOScheduler
# 从 binance.spot 模块导入 Spot 类，用于与 Binance 现货交易 API 交互
from binance.spot import Spot
# 从 jsonpath_ng 模块导入 parse 函数，用于解析 JSON 数据
from jsonpath_ng import parse


def trade(symbol, price, stopPrice, symbols_info, slot):
    """
    执行交易操作，包括买入和卖出订单的创建

    :param symbol: 交易对符号
    :param price: 卖出价格
    :param stopPrice: 止损价格
    :param symbols_info: 交易对信息字典
    :param slot: 仓位比例
    :return: 若交易成功返回交易对符号，否则返回 None
    """
    try:
        # 获取 USDT 可用余额，若余额小于 6 则不进行交易
        if (usdt_free := float(spotBN.user_asset(asset='USDT')[0]['free'])) < 6:
            return
        # 根据仓位比例计算可用 USDT 金额，若计算后金额大于等于 6 则更新可用余额
        elif (usdt_slot := usdt_free * slot) >= 6:
            usdt_free = usdt_slot
        else:
            return
        # 获取交易对的最小交易数量精度
        minQty = symbols_info.get(symbol).get('minQty')
        # 获取交易对的报价精度
        quotePrecision = symbols_info.get(symbol).get('quotePrecision')
        # 构建买入订单参数
        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quoteOrderQty": round(usdt_free, quotePrecision)
        }
        # 发送买入订单请求
        spotBN.new_order(**params)
        # 等待 3 秒，确保订单处理完成
        time.sleep(3)
        for _ in range(3):
            try:
                # 获取交易对资产的可用余额
                symbol_free = spotBN.user_asset(asset=symbol[:-4])[0]['free']
                # 对可用余额进行精度处理
                symbol_free_round = float(
                    Decimal(symbol_free).quantize(Decimal(f'0.{"1" * minQty}'), rounding=ROUND_DOWN))
                # 构建卖出订单参数
                params = {
                    "symbol": symbol,
                    "side": "SELL",
                    "quantity": symbol_free_round,
                    "price": price,
                    "stopPrice": stopPrice
                }
                # 发送卖出订单请求
                spotBN.new_oco_order(**params)
                return symbol
            except:
                # 打印异常堆栈信息
                traceback.print_exc()
                # 等待 2 秒后重试
                time.sleep(2)
    except:
        # 打印异常堆栈信息
        traceback.print_exc()
        return


async def get_kline(semaphore, symbol, t: str):
    """
    异步获取指定交易对的 K 线数据

    :param semaphore: 异步信号量，用于控制并发数量
    :param symbol: 交易对符号
    :param t: K 线时间周期，如 "1Dutc"
    :return: K 线数据列表，元素为浮点数列表
    """
    async with semaphore:
        # 异步调用 spotBN.klines 方法获取 K 线数据
        kline = await asyncio.to_thread(spotBN.klines, symbol=symbol, interval=t[:2].lower(), limit=20)
        # kline = await asyncio.to_thread(spotBN.klines, symbol=symbol, interval=t[:2].lower(), limit=20,
        #                                 endTime=1747699200000)
        # 将 K 线数据中的元素转换为浮点数
        kline = [list(map(float, sublist)) for sublist in kline]
        return kline


def calculate_ema_pandas(prices, period=None):
    """
    使用 pandas 计算指数移动平均线 (EMA)

    :param prices: 价格数据列表
    :param period: 计算 EMA 的周期，默认为价格数据列表的长度
    :return: 最后一个 EMA 值
    """
    # 将价格数据转换为 pandas Series 对象
    df = pd.Series(prices)
    if not period:
        period = len(prices)
    # 计算 EMA
    ema = df.ewm(span=period, adjust=False).mean()
    # 返回最后一个 EMA 值
    return ema.tolist()[-1]


async def rzq_token(semaphore, symbol, alert, success, alert_m, symbols_info):
    """
    异步分析指定交易对的 K 线数据，筛选符合条件的交易对

    :param semaphore: 异步信号量，用于控制并发数量
    :param symbol: 交易对符号
    :param alert: 存储符合条件的交易对信息的字典
    :param success: 存储成功获取 K 线数据的交易对集合
    :param alert_m: 存储需要进一步处理的交易对信息的字典
    :return: 若不符合条件则返回 None，否则返回符合条件的交易对信息字典
    """
    try:
        # 异步获取指定交易对的 K 线数据
        kline = await get_kline(semaphore, symbol, "1Dutc")
        # 将成功获取 K 线数据的交易对添加到集合中
        success.add(symbol)
        # 若 K 线数据长度小于 20 或收盘价小于等于开盘价，则不进行后续分析
        if len(kline) < 20:
            return
        # 初始化结束索引
        index_e = 0
        # 获取 K 线数据中的收盘价列表
        kline_close = [k[4] for k in kline]
        # 计算 K 线数据的涨跌幅列表
        kline_zf = list(map(lambda k: k[4] / k[1] - 1, kline))
        # 获取 K 线数据中的量能列表
        kline_vol = [k[5] for k in kline]
        # 从倒数第 5 个到倒数第 9 个 K 线数据中寻找符合条件的起始索引
        for i, k in enumerate(kline[-5:-9:-1]):
            if k[4] > k[1] and kline_close[-i - 5] > max(kline_close[:-i - 5]) and k[5] >= max(kline_vol[:-i - 5]) * 2:
                index_e = -i - 5
                # 初始化起始索引
                index_s = index_e
                # 从起始索引往前遍历，寻找符合条件的结束索引
                for ii, kk in enumerate(kline[index_e - 1::-1]):
                    if index_e - ii - 1 == -20:
                        if kk[4] <= kk[1]:
                            index_s = -19
                        else:
                            index_s = -20
                    elif kk[4] <= kk[1] and kline_zf[index_e - ii - 2] <= 0:
                        index_s = index_e - ii
                        break
                break
        # 若未找到符合条件的索引或存在不符合条件的 K 线数据，则不进行后续分析
        if not index_e or kline_zf[-2] <= 0 or kline_zf[-3] <= 0:
            return
        # 获取最新收盘价
        price_close = kline[-1][4]
        # 若前一日最高价大于等于最新收盘价，则不进行后续分析
        if any(x > 0 and y > 0 for x, y in pairwise(kline_zf[index_e + 1:-2])):
            return
        # 计算收盘价的最大小数位数
        max_decimal = symbols_info.get(symbol).get('maxDecimal')
        # 截取符合条件的涨跌幅列表
        kline_zf = kline_zf[index_s:-1]
        # 计算正向涨跌幅的 EMA 并乘以 0.9
        zf_z = calculate_ema_pandas([k if k > 0 else 0 for k in kline_zf])
        # 计算 K 线数据的高低价差涨跌幅的 EMA
        zf_d = calculate_ema_pandas([(k[3] - k[1]) / k[1] for k in kline[index_s:-1]])
        # 计算预期价格
        price_zy = round(kline[-2][4] + kline[-2][4] * zf_z, max_decimal)
        # 计算预期收益率
        expectation = round((price_zy / kline[-1][2] - 1) * 100, 2)
        if expectation <= 0:
            return
        # 计算止损价格
        # price_zs = round(kline[-2][4] + kline[-2][4] * zf_d, max_decimal)
        price_zs = round(kline[-1][2] * symbols_info.get(symbol).get('askMultiplierDown'), max_decimal)
        price_zs = max(price_zs, min(kline[-3][3], kline[-2][3]))
        # 计算风险收益率
        risk = round((price_zs / kline[-1][2] - 1) * 100, 2)
        # 计算仓位状态的 EMA
        size_z = calculate_ema_pandas([1 if k > 0 else 0 for k in kline_zf])
        if size_z == 1:
            size_z = 0.9
        # 计算仓位比例
        slot = (expectation * size_z + risk * (1 - size_z)) / expectation
        if slot <= 0:
            return
        # 构建符合条件的交易对信息字典
        data = {symbol: (price_close, expectation, risk, price_zy, price_zs, slot)}
        # 更新符合条件的交易对信息字典
        alert.update(data)
        # 更新需要进一步处理的交易对信息字典
        alert_m.update(data)
        return data
    except:
        # 打印异常堆栈信息
        traceback.print_exc()
        return


def get_minQty(minQty):
    """
    计算最小交易数量的精度

    :param minQty: 包含最小交易数量的列表
    :return: 最小交易数量的精度，即小数位数
    """
    # 将列表中的元素转换为 Decimal 类型并标准化，取最大值
    minQty = max(map(lambda x: Decimal(x).normalize(), minQty))
    # 返回最小交易数量的小数位数
    return -minQty.as_tuple().exponent


async def rzq_market(market):
    """
    异步执行市场分析任务，筛选符合条件的交易对并进行交易操作，最后记录结果并发送通知

    :param market: 市场名称，如 'BN'
    """
    # 获取当前时间
    now = datetime.datetime.now()
    # 初始化交易对列表
    symbols = []
    # 获取当前市场的交易对信息字典，若不存在则初始化为空字典
    alert = alert_all.get(market, {})
    # 获取当前持仓信息字典，若不存在则初始化为空字典
    POSITIONS = alert_all.get("POSITIONS", {})
    # 获取当前交易记录列表，若不存在则初始化为空列表
    TRADING = alert_all.get("TRADING", [])
    # 若当前时间为 8 点且分钟数小于 2，则清空相关数据
    if now.hour == 8 and now.minute < 2:
        alert.clear()
        POSITIONS.clear()
        TRADING.clear()
    # 最多尝试 10 次获取交易对信息
    for i in range(10):
        try:
            # 异步调用 spotBN.exchange_info 方法获取所有交易对信息
            exchange_info = await asyncio.to_thread(spotBN.exchange_info)
            # 提取符合条件的交易对信息，构建交易对信息字典
            symbols_info = {symbol['symbol']: {'quotePrecision': symbol['quotePrecision'],
                                               'askMultiplierDown': float(
                                                   parse('$..askMultiplierDown').find(symbol)[0].value),
                                               'minPrice': float(parse('$..minPrice').find(symbol)[0].value),
                                               'maxDecimal': get_minQty(
                                                   [y.value for y in parse('$..minPrice').find(symbol)]),
                                               'minQty': get_minQty([y.value for y in parse('$..minQty').find(symbol)])}
                            for symbol in exchange_info['symbols'] if
                            symbol['symbol'] not in POSITIONS and 'USDT' in symbol['quoteAsset'] and 'TRADING' in
                            symbol['status']}
            # 获取符合条件的交易对列表
            symbols = list(symbols_info.keys())
            break
        except:
            # 打印异常堆栈信息，等待 2 秒后重试
            traceback.print_exc()
            await asyncio.sleep(2)
    # 创建异步信号量，限制并发数量为 10
    semaphore = asyncio.Semaphore(10)
    # 打印任务开始信息
    print(now, f'{market}任务开始', len(symbols))
    # 初始化成功获取 K 线数据的交易对集合
    success = set()
    # 初始化需要进一步处理的交易对信息字典
    alert_m = {}
    # 初始化最终结果列表
    alert_final = []
    # 创建异步任务列表
    tasks = [rzq_token(semaphore, symbol, alert, success, alert_m, symbols_info) for symbol in symbols]
    # 并发执行所有任务
    await asyncio.gather(*tasks)
    try:
        # 打印成功获取 K 线数据的交易对数量信息
        print(market, f"""{len(success)}/{len(symbols)}""")
        if alert_m:
            # 对符合条件的交易对按仓位比例排序
            alert_sort = enumerate(sorted(alert, key=lambda x: alert[x][5], reverse=True))
            for i, j in alert_sort:
                if j not in alert_m:
                    continue
                if j not in POSITIONS:
                    # 执行交易操作，若成功则更新持仓信息
                    if trade(symbol=j, price=alert_m[j][3], stopPrice=alert_m[j][4], symbols_info=symbols_info,
                             slot=alert_m[j][5]):
                        POSITIONS.update({j: alert_m[j]})
                if j in POSITIONS:
                    # 构建开仓交易对信息字符串并添加到最终结果列表
                    alert_final.append(
                        f'开仓{i + 1}.{j.replace("-USDT", "USDT")[:-4]}\n'
                        f'现价:{alert_m[j][0]}\n预期:{alert_m[j][1]}\n风险:{alert_m[j][2]}\n止盈:{alert_m[j][3]}\n止损:{alert_m[j][4]}\n仓位:{alert_m[j][5]}')
                elif j not in TRADING:
                    # 构建交易对信息字符串并添加到最终结果列表
                    alert_final.append(
                        f'{i + 1}.{j.replace("-USDT", "USDT")[:-4]}\n'
                        f'现价:{alert_m[j][0]}\n预期:{alert_m[j][1]}\n风险:{alert_m[j][2]}\n止盈:{alert_m[j][3]}\n止损:{alert_m[j][4]}\n仓位:{alert_m[j][5]}')
                    # 将交易对添加到交易记录列表
                    TRADING.append(j)
            if alert_final:
                # 构建企业微信消息内容
                json_msg = {
                    "msgtype": "text",
                    "text": {'content': f'==={market}{len(alert)}做多===\n' + '\n-------\n'.join(alert_final)}
                }
                # 发送企业微信消息
                session.post(
                    url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
                    json=json_msg)
        elif not success and symbols:
            # 构建交易失败信息列表
            alert_final = [f"""{len(success)}/{len(symbols)}"""]
            # 构建企业微信消息内容
            json_msg = {
                "msgtype": "text",
                "text": {'content': f'==={market}{len(alert)}===\n' + '\n-------\n'.join(alert_final)}
            }
            # 发送企业微信消息
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
                json=json_msg)
    finally:
        # 将符合条件的交易对信息保存到 JSON 文件
        with open('symbol.json', 'w') as f:
            json.dump(alert, f, indent=4, ensure_ascii=False)
        # 打印任务结束信息
        print(datetime.datetime.now(), f'{market}任务结束', alert_final, alert)
        # 进行垃圾回收
        gc.collect()


# 辅助函数：获取股票涨停价
def get_upper_limit(code, stock_info):
    """
    根据股票代码和股票信息计算涨停价

    :param code: 股票代码
    :param stock_info: 包含股票名称和昨收价格的 DataFrame
    :return: 股票的涨停价，保留两位小数
    """
    # 获取股票名称
    name = stock_info['名称'].values[0]
    # 获取股票昨收价格
    prev_close = stock_info['昨收'].values[0]
    if 'ST' in name or '*ST' in name:
        # ST 股涨停 5%
        return round(prev_close * 1.05, 2)
    elif code.startswith(('300', '688')):
        # 创业板和科创板涨停 20%
        return round(prev_close * 1.2, 2)
    else:
        # 其他股票涨停 10%
        return round(prev_close * 1.1, 2)


def get_last_trading_days(today=None, days=60):
    """
    获取最近的交易日信息

    :param today: 指定日期，默认为当前日期
    :param days: 获取最近交易日的天数，默认为 60 天
    :return: 起始日期、结束日期和涨停股查询日期列表
    """
    if not today:
        today = datetime.datetime.today()
    # 获取最近的交易日列表
    trade_dates = ak.tool_trade_date_hist_sina()
    # 将交易日期转换为 datetime 类型
    trade_dates = pd.to_datetime(trade_dates["trade_date"])
    # 找到最近的指定天数的交易日
    recent_trading_days = trade_dates[trade_dates <= today].sort_values(ascending=False).iloc[:days]
    # 获取起始日期
    start_date = recent_trading_days.min().strftime("%Y%m%d")
    # 获取结束日期
    end_date = recent_trading_days.max().strftime("%Y%m%d")
    # 获取涨停股查询日期列表
    zt_date = [i.strftime("%Y%m%d") for i in recent_trading_days.iloc[3:7]]
    # 返回起始日期、结束日期和涨停股查询日期列表
    return start_date, end_date, zt_date


# 步骤2：筛选符合条件的股票
def filter_stocks():
    """
    筛选符合量能条件的股票

    :return: 符合条件的股票代码和名称集合
    """
    # 获取最近交易日信息
    start_date, end_date, zt_dates = get_last_trading_days()
    # 可取消注释以下行，指定特定日期获取相关信息
    # start_date, end_date, zt_dates = get_last_trading_days(datetime.datetime.strptime('20250514', '%Y%m%d'))
    # 初始化符合条件的股票集合
    selected = set()
    for i, zt_date in enumerate(zt_dates):
        # 使用 akshare 库获取指定日期的涨停股信息
        zt_df = ak.stock_zt_pool_em(date=zt_date)
        # 检查获取的涨停股信息 DataFrame 是否为空
        if zt_df.empty:
            # 若为空，打印提示信息，表示在指定日期未找到涨停股票
            print(f"没有在 {zt_date} 找到涨停股票。")
            continue
        # 获取涨停股的代码和名称列表
        stock_codes = zt_df[['代码', '名称']].values.tolist()
        print(f"{zt_date}涨停股：{stock_codes}")
        # spot_df = ak.stock_zh_a_spot()
        for code in stock_codes:
            try:
                # 获取历史数据（昨日量能）
                hist = ak.stock_zh_a_hist(symbol=code[0], period="daily", start_date=start_date, end_date=end_date,
                                          adjust="qfq")
            except:
                # 打印异常堆栈信息
                traceback.print_exc()
                continue
            print(code, hist.iloc[-1]['涨跌幅'])
            if len(hist) < 60 or hist.iloc[-2:]['涨跌幅'].min() <= 0 or hist.iloc[:-i - 4]['收盘'].max() > \
                    hist.iloc[-i - 4]['收盘'] or any(
                x > 0 and y > 0 for x, y in pairwise(hist.iloc[-i - 3:-1]['涨跌幅'].tolist())):
                continue
            # today_close = hist.iloc[-1]['收盘']
            # today_open = hist.iloc[-1]['开盘']
            # yesterday_close = hist.iloc[-2]['收盘']
            # yesterday_open = hist.iloc[-2]['开盘']
            # 获取今日实时数据
            # spot_data = spot_df[spot_df['代码'].str.contains(code)]
            # if spot_data.empty: continue

            # today_vol = spot_data['成交量'].values[0]
            # today_pct = spot_data['涨跌幅'].values[0]
            # 将符合条件的股票代码和名称添加到集合中
            selected.add(''.join(code))
    return selected


# 步骤3：实时监控
def monitor_stocks():
    """
    实时监控符合量能条件的股票，并通过企业微信发送通知
    """
    # 筛选符合量能条件的股票
    filtered = filter_stocks()
    print(f"符合量能条件的股票：{filtered}")
    if filtered:
        # 构建企业微信消息内容
        json_msg = {
            "msgtype": "text",
            "text": {'content': f'===A{len(filtered)}低吸===\n' + '\n-------\n'.join(filtered)}
        }
        # 发送企业微信消息
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
            json=json_msg)


async def main():
    """
    主函数，启动股票监控和市场分析任务，并设置定时任务
    """
    # 执行股票监控任务
    monitor_stocks()
    # 执行市场分析任务
    await rzq_market('BN')
    # 设置任务调度
    scheduler.add_job(monitor_stocks, 'cron', hour='14', minute='52-57', second='00', day_of_week='mon-fri',
                      timezone='Asia/Shanghai')
    scheduler.add_job(rzq_market, 'cron', hour='08', minute='*/30', second='00', timezone='Asia/Shanghai',
                      args=('BN',))
    # 启动调度器
    scheduler.start()
    # 创建异步事件
    stop_event = asyncio.Event()
    # 等待事件触发
    await stop_event.wait()


if __name__ == "__main__":
    # 创建 requests 会话
    session = requests.Session()
    # 禁用 SSL 验证
    session.verify = False
    # 设置请求头
    session.headers = {'Content-Type': 'application/json'}
    # 创建 AsyncIOScheduler 对象
    scheduler = AsyncIOScheduler()
    # 从文件中读取 Binance API 信息
    with open('bn.json', 'r') as f:
        bn_api = json.load(f)
    # 创建 Binance Spot 客户端
    spotBN = Spot(api_key=bn_api.get('api_key'), api_secret=bn_api.get('api_secret'))
    # 初始化全局信息字典
    alert_all = {'BN': {}, 'POSITIONS': {}, 'TRADING': []}
    # 运行异步主函数
    asyncio.run(main())
