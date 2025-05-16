import asyncio
import datetime
import gc
import json
import time
import traceback
from decimal import Decimal, ROUND_DOWN

import akshare as ak
import pandas as pd
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from binance.spot import Spot
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
        while True:
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
                    "stopPrice": max(stopPrice, float(
                        Decimal(6 / symbol_free_round).quantize(Decimal(f'{stopPrice}'), rounding=ROUND_DOWN)))
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


async def rzq_token(semaphore, symbol, alert, success, alert_m):
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
        index_e = 0
        # 计算 K 线数据的涨跌幅列表
        kline_zf = list(map(lambda k: k[4] / k[1] - 1, kline))
        # 获取 K 线数据中的收盘价列表
        kline_close = [k[4] for k in kline]
        # 遍历 K 线数据，寻找符合条件的起始索引
        for i, k in enumerate(kline[-5:-9:-1]):
            if k[4] > k[1] and kline_zf[-i - 5] > max(kline_zf[:-i - 5]) and k[4] >= max(kline_close[:-i - 5]):
                index_e = -i - 5
                index_s = index_e
                # 从起始索引往前遍历，寻找符合条件的结束索引
                for ii, kk in enumerate(kline[index_e - 1::-1]):
                    if index_e - ii == -20:
                        index_s = -20
                    elif kk[4] <= kk[1] and kline_zf[index_e - ii - 1] <= 0:
                        index_s = index_e - ii
                        break
                break
        # 若未找到符合条件的索引或存在不符合条件的 K 线数据，则不进行后续分析
        if not index_e or kline_zf[-2] <= 0 or kline_zf[
            -3] <= 0:  # or list(filter(lambda x: kline[index_e][3] > x[4], kline[index_e + 1:-1])):
            return
        # 获取最新收盘价
        price_close = kline[-1][4]
        # 若前一日最高价大于等于最新收盘价，则不进行后续分析
        if max(kline[-2][2], kline[-3][2]) >= max([k[2] for k in kline[index_e:index_e + 2]]):
            return
        if index_e == -5 and kline_zf[index_e + 1] > 0:
            return
        elif index_e < -5 and max(kline_zf[index_e + 2:-3]) > 0:
            return
        # 计算收盘价的最大小数位数
        max_decimal = max(map(lambda ks: -Decimal(str(ks)).normalize().as_tuple().exponent, kline_close))
        # 计算 K 线数据的涨跌幅列表
        kline_zf = kline_zf[index_s:-1]
        zf_z = calculate_ema_pandas([k if k > 0 else 0 for k in kline_zf]) * 0.9
        zf_d = calculate_ema_pandas([(k[3] - k[1]) / k[1] for k in kline[index_s:-1]])
        price_zy = round(kline[-2][4] + kline[-2][4] * zf_z, max_decimal)
        expectation = round((price_zy / kline[-1][2] - 1) * 100, 2)
        if expectation <= 0:
            return
        if price_zy > kline[-1][2]:
            price_zs = round(kline[-2][4] + kline[-2][4] * zf_d, max_decimal)
            risk = round((price_zs / kline[-1][2] - 1) * 100, 2)
            size_z = calculate_ema_pandas([1 if k > 0 else 0 for k in kline_zf])
            if size_z == 1:
                size_z = 0.9
            slot = (expectation * size_z + risk * (1 - size_z)) / expectation
            if slot <= 0:
                return
            data = {symbol: (price_close, expectation, risk, price_zy, price_zs, slot)}
            alert.update(data)
            alert_m.update(data)
            return data
    except:
        traceback.print_exc()
        return


def get_minQty(minQty):
    minQty = max(map(lambda x: Decimal(x).normalize(), minQty))
    return -minQty.as_tuple().exponent


async def rzq_market(market):
    now = datetime.datetime.now()
    symbols = []
    alert = alert_all.get(market, {})
    POSITIONS = alert_all.get("POSITIONS", {})
    TRADING = alert_all.get("TRADING", [])
    if now.hour == 8 and now.minute < 2:
        alert.clear()
        POSITIONS.clear()
        TRADING.clear()
    for i in range(10):
        try:
            # 获取所有交易对信息
            exchange_info = await asyncio.to_thread(spotBN.exchange_info)
            # 提取所有交易对
            symbols_info = {symbol['symbol']: {'quotePrecision': symbol['quotePrecision'],
                                               'minQty': get_minQty([y.value for y in parse('$..minQty').find(symbol)])}
                            for symbol in exchange_info['symbols'] if
                            symbol['symbol'] not in POSITIONS and 'USDT' in symbol['quoteAsset'] and 'TRADING' in
                            symbol[
                                'status']}
            symbols = list(symbols_info.keys())
            break
        except:
            traceback.print_exc()
            await asyncio.sleep(2)
    semaphore = asyncio.Semaphore(10)  # 限制 2 个并发
    print(now, f'{market}任务开始', len(symbols))
    success = set()
    alert_m = {}
    alert_final = []
    tasks = [rzq_token(semaphore, symbol, alert, success, alert_m) for symbol in symbols]
    await asyncio.gather(*tasks)
    try:
        print(market, f"""{len(success)}/{len(symbols)}""")
        if alert_m:
            alert_sort = enumerate(sorted(alert, key=lambda x: alert[x][5], reverse=True))
            for i, j in alert_sort:
                if j not in alert_m:
                    continue
                if j not in POSITIONS:
                    if trade(symbol=j, price=alert_m[j][3], stopPrice=alert_m[j][4], symbols_info=symbols_info,
                             slot=alert_m[j][5]):
                        POSITIONS.update({j: alert_m[j]})
                if j in POSITIONS:
                    alert_final.append(
                        f'开仓{i + 1}.{j.replace("-USDT", "USDT")[:-4]}\n'
                        f'现价:{alert_m[j][0]}\n预期:{alert_m[j][1]}\n风险:{alert_m[j][2]}\n止盈:{alert_m[j][3]}\n止损:{alert_m[j][4]}\n仓位:{alert_m[j][5]}')
                elif j not in TRADING:
                    alert_final.append(
                        f'{i + 1}.{j.replace("-USDT", "USDT")[:-4]}\n'
                        f'现价:{alert_m[j][0]}\n预期:{alert_m[j][1]}\n风险:{alert_m[j][2]}\n止盈:{alert_m[j][3]}\n止损:{alert_m[j][4]}\n仓位:{alert_m[j][5]}')
                    TRADING.append(j)
            if alert_final:
                json_msg = {
                    "msgtype": "text",
                    "text": {'content': f'==={market}{len(alert)}做多===\n' + '\n-------\n'.join(alert_final)}
                }
                session.post(
                    url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
                    json=json_msg)
        elif not success and symbols:
            alert_final = [f"""{len(success)}/{len(symbols)}"""]
            json_msg = {
                "msgtype": "text",
                "text": {'content': f'==={market}{len(alert)}===\n' + '\n-------\n'.join(alert_final)}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
                json=json_msg)
    finally:
        with open('symbol.json', 'w') as f:
            json.dump(alert, f, indent=4, ensure_ascii=False)
        print(datetime.datetime.now(), f'{market}任务结束', alert_final, alert)
        gc.collect()


# 辅助函数：获取股票涨停价
def get_upper_limit(code, stock_info):
    name = stock_info['名称'].values[0]
    prev_close = stock_info['昨收'].values[0]
    if 'ST' in name or '*ST' in name:
        return round(prev_close * 1.05, 2)  # ST股涨停5%
    elif code.startswith(('300', '688')):  # 创业板和科创板涨停20%
        return round(prev_close * 1.2, 2)
    else:  # 其他股票涨停10%
        return round(prev_close * 1.1, 2)


def get_last_trading_days(today=None, days=60):
    if not today:
        today = datetime.datetime.today()
    # 获取最近的交易日列表
    trade_dates = ak.tool_trade_date_hist_sina()
    trade_dates = pd.to_datetime(trade_dates["trade_date"])  # 转换为 datetime
    # 找到最近的三个交易日
    recent_trading_days = trade_dates[trade_dates <= today].sort_values(ascending=False).iloc[:days]
    start_date = recent_trading_days.min().strftime("%Y%m%d")
    end_date = recent_trading_days.max().strftime("%Y%m%d")
    zt_date = [i.strftime("%Y%m%d") for i in recent_trading_days.iloc[3:7]]
    # 返回起始日期、结束日期和涨停股查询日期
    return start_date, end_date, zt_date


# 步骤2：筛选符合条件的股票
def filter_stocks():
    # 获取最近交易日（这里假设昨日是20231009，实际应自动获取）
    start_date, end_date, zt_dates = get_last_trading_days()
    # 可取消注释以下行，指定特定日期获取相关信息
    # start_date, end_date, zt_dates = get_last_trading_days(datetime.datetime.strptime('20250508', '%Y%m%d'))
    # 使用 akshare 库获取指定日期的涨停股信息
    selected = set()
    for i, zt_date in enumerate(zt_dates):
        zt_df = ak.stock_zt_pool_em(date=zt_date)
        # 检查获取的涨停股信息 DataFrame 是否为空
        if zt_df.empty:
            # 若为空，打印提示信息，表示在指定日期未找到涨停股票
            print(f"没有在 {zt_date} 找到涨停股票。")
            continue
        stock_codes = zt_df[['代码', '名称']].values.tolist()
        print(f"{zt_date}涨停股：{stock_codes}")
        # spot_df = ak.stock_zh_a_spot()
        for code in stock_codes:
            try:
                # 获取历史数据（昨日量能）
                hist = ak.stock_zh_a_hist(symbol=code[0], period="daily", start_date=start_date, end_date=end_date,
                                          adjust="qfq")
            except:
                traceback.print_exc()
                continue
            print(code, hist.iloc[-1]['涨跌幅'])
            if len(hist) < 60 or hist.iloc[-2:]['涨跌幅'].min() <= 0 or hist.iloc[:-i - 4]['收盘'].max() > \
                    hist.iloc[-i - 4]['收盘']: continue
            if i == 0 and hist.iloc[- 3]['涨跌幅'].max() > 0:
                continue
            elif hist.iloc[-i - 2:-2]['涨跌幅'].max() > 0:
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
            if hist.iloc[-2:]['最高'].max() < hist.iloc[-i - 4:-i - 2]['最高'].max():
                selected.add(''.join(code))
    return selected


# 步骤3：实时监控
def monitor_stocks():
    filtered = filter_stocks()
    print(f"符合量能条件的股票：{filtered}")
    if filtered:
        json_msg = {
            "msgtype": "text",
            "text": {'content': f'===A{len(filtered)}低吸===\n' + '\n-------\n'.join(filtered)}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
            json=json_msg)


async def main():
    monitor_stocks()
    await rzq_market('BN')
    # 设置任务调度
    scheduler.add_job(monitor_stocks, 'cron', hour='14', minute='52-57', second='00', day_of_week='mon-fri',
                      timezone='Asia/Shanghai')
    scheduler.add_job(rzq_market, 'cron', hour='*', minute='*/1', second='00', timezone='Asia/Shanghai',
                      args=('BN',))
    # 启动调度器
    scheduler.start()
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发


if __name__ == "__main__":
    session = requests.Session()
    session.verify = False
    session.headers = {'Content-Type': 'application/json'}
    # 创建BlockingScheduler对象
    scheduler = AsyncIOScheduler()
    with open('bn.json', 'r') as f:
        bn_api = json.load(f)
    spotBN = Spot(api_key=bn_api.get('api_key'), api_secret=bn_api.get('api_secret'))
    alert_all = {'BN': {}, 'POSITIONS': {}, 'TRADING': []}
    asyncio.run(main())
