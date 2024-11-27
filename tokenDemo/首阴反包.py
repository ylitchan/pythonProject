import datetime
import gc
import json
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import baostock as bs
import okx.MarketData as MarketData
import okx.PublicData as PublicData
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from binance.spot import Spot
from jsonpath_ng import parse
from lxml import etree


def klines_a(symbol):
    #### 获取历史K线数据 ####
    # 详细指标参数，参见“历史行情指标参数”章节
    rs = bs.query_history_k_data_plus(symbol,  # 股票代码
                                      "preclose, open, high, low, close, volume",
                                      # 要获取的参数
                                      start_date=(datetime.datetime.now() - datetime.timedelta(days=30)).strftime(
                                          '%Y-%m-%d'), end_date=datetime.datetime.now().strftime('%Y-%m-%d'),
                                      # 开始时间，结束时间
                                      frequency="d", adjustflag="3")  # frequency="d"取日k线，adjustflag="3"默认不复权
    data_list = []
    while (rs.error_code == '0') & rs.next():
        # 获取一条记录，将记录合并在一起
        data_list.append(rs.get_row_data())
    return data_list


# 判断多头排列
def is_golden_cross(data, short_window=5, mid_window=10, long_window=20):
    if len(data) < long_window:
        return None
    short_ma = statistics.mean(data[-short_window:])
    mid_ma = statistics.mean(data[-mid_window:])
    long_ma = statistics.mean(data[-long_window:])
    # 判定是否满足多头排列条件
    return not list(filter(
        lambda x: statistics.mean(data[x[0] + 1 - short_window:x[0] + 1]) > x[-1] if len(data) - 1 > x[0] > len(
            data) - 1 - short_window else False, enumerate(data))) and len(list(filter(
        lambda x: x[-1] <= data[x[0] - 1] if len(data) - 1 > x[0] > len(data) - 1 - short_window else False,
        enumerate(data)))) == 1 and data[-2] <= data[-3]


def get_kline(symbol, t: str):
    if "-USDT" in symbol:
        kline = [list(map(float, sublist)) for sublist in
                 marketDataAPI.get_candlesticks(instId=symbol, bar=t, limit=20).get('data')[::-1]]
    elif "USDT" in symbol:
        kline = [list(map(float, sublist)) for sublist in
                 client.klines(symbol=symbol, interval=t[:2].lower(), limit=20)]
    else:
        kline = [list(map(float, sublist)) for sublist in klines_a(symbol)]
    return kline


def get_max_decimal_places(price_s):
    if p := re.search('\.\d+', price_s):
        return len(p.group()) - 1
    return 0


def rzq_token(symbol, alert, success):
    if symbol in alert:
        success.add(symbol)
        return
    try:
        kline = get_kline(symbol, "1Dutc")
        kline_close = [k[4] for k in kline]
        max_decimal = max(map(get_max_decimal_places, map(str, kline_close)))
        price_close = kline[-1][4]
        price_vol = kline[-2][1]
        zf = round((kline[-3][4] / kline[-5][1] - 1) * 100, 2)
        zf_m = statistics.median([round((k[4] / k[1] - 1) * 100, 2) for k in kline[-5:-2]])
        price_zy = round(price_close + price_vol * zf_m / 100, max_decimal)
        price_zs = round(price_close - price_vol * zf_m / 100, max_decimal)
        success.add(symbol)
        if zf >= 0 and price_close > max([k[1] for k in kline[-2:-1]]) and is_golden_cross(kline_close):
            alert.update({symbol: (price_close, zf, price_zy, price_zs)})
            return {symbol: (price_close, zf, price_zy, price_zs)}
    except:
        return


def rzq_market(market, symbols, job):
    print(datetime.datetime.now(), f'{market}任务开始', len(symbols))
    alert = alert_all.get(market, {})
    if datetime.datetime.now().hour == 8 and datetime.datetime.now().minute < 2:
        alert.clear()
    success = set()
    alert_m = {}
    alert_final = []
    thread_pool = ThreadPoolExecutor(max_workers=100)
    futures = [thread_pool.submit(job, symbol, alert, success) for symbol in symbols if symbol not in alert]
    for future in as_completed(futures):
        if r := future.result():
            alert_m.update(r)
    thread_pool.shutdown()
    try:
        print(market, f"""{len(success)}/{len(symbols)}""")
        if alert_m:
            alert_sort = enumerate(sorted(alert, key=lambda x: alert[x][1], reverse=True))
            for i, j in alert_sort:
                if j not in alert_m:
                    continue
                if 'USDT' in j:
                    alert_final.append(
                        f'{i + 1}.{j.replace("-USDT", "USDT")[:-4]}\n'
                        f'现价:{alert_m[j][0]}\n涨幅:{alert_m[j][1]}\n止盈:{alert_m[j][2]}\n止损:{alert_m[j][3]}')
                else:
                    alert_final.append(
                        f'{i + 1}.{j}\n现价:{alert_m[j][0]}\n涨幅:{alert_m[j][1]}\n止盈:{alert_m[j][2]}\n止损:{alert_m[j][3]}')
            json_msg = {
                "msgtype": "text",
                "text": {'content': f'==={market}{len(alert)}===\n' + '\n-------\n'.join(alert_final)}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=4499f04a-88cf-4100-aef3-7528b2a94d67',
                json=json_msg)
        elif not success and symbols:
            alert_final = [f"""{len(success)}/{len(symbols)}"""]
            json_msg = {
                "msgtype": "text",
                "text": {'content': f'==={market}{len(alert)}===\n' + '\n-------\n'.join(alert_final)}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=4499f04a-88cf-4100-aef3-7528b2a94d67',
                json=json_msg)
    finally:
        print(datetime.datetime.now(), f'{market}任务结束', alert_final, alert)
        gc.collect()


def main():
    # symbols_a = [c[0] for c in bs.query_all_stock().data if 'ST' not in c[-1]]
    symbols_bn = []
    symbols_okx = []
    for i in range(10):
        try:
            res = session.get('https://www.binance.com/zh-CN/markets/overview?p=1')
            data = json.loads(etree.HTML(res.text).xpath('//*[@id="__APP_DATA"]//text()')[0])
            symbols_bn = [item['symbol'] for item in parse('$..productMap').find(data)[0].value.values() if
                          item.get('quoteAsset') == 'USDT']
            symbols_okx = [item['instId'] for item in publicDataAPI.get_instruments(
                instType="SPOT"
            ).get('data') if item.get('quoteCcy') == 'USDT']
            break
        except Exception:
            time.sleep(2)
    # rzq_market('A', symbols_a, rzq_token)
    rzq_market('BN', symbols_bn, rzq_token)
    # rzq_market('OKX', symbols_okx, rzq_token)
    # 设置任务调度
    # scheduler.add_job(rzq_market, 'cron', hour='9-15', minute='*/5', second='00', day_of_week='mon-fri',
    #                   timezone='Asia/Shanghai', args=['A', symbols_a, rzq_token])
    scheduler.add_job(rzq_market, 'cron', hour='*', minute='*/1', second='00', timezone='Asia/Shanghai',
                      args=['BN', symbols_bn, rzq_token])
    # scheduler.add_job(rzq_market, 'cron', hour='*', minute='*/15', second='00', timezone='Asia/Shanghai',
    #                   args=['OKX', symbols_okx, rzq_token])
    # 启动调度器
    scheduler.start()


if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    session = requests.Session()
    session.verify = False
    session.headers = {'Content-Type': 'application/json',
                       'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'}
    # 创建BlockingScheduler对象
    scheduler = BlockingScheduler()
    bs.login()
    bs.logout()
    client = Spot()
    marketDataAPI = MarketData.MarketAPI(flag='0', debug=False)
    publicDataAPI = PublicData.PublicAPI(flag='0', debug=False)
    alert_all = {'BN': {}, 'OKX': {}, 'A': {}}
    main()
