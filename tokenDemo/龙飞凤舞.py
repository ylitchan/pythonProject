import datetime
import gc
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import okx.MarketData as MarketData
import okx.PublicData as PublicData
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from binance.spot import Spot
from jsonpath_ng import parse
from lxml import etree


def rzq_a():
    try:
        print(datetime.datetime.now(), 'A任务开始')
        json_msg = {
            "msgtype": "news",
            "news": {
                "articles": [
                    {
                        "title": "主人，请享用[害羞]",
                        "description": "",
                        "url": "https://www.iwencai.com/unifiedwap/result?w=5%E6%97%A510%E6%97%A520%E6%97%A5%E7%9A%84"
                               "%E5%9D%87%E7%BA%BF%E5%A4%9A%E5%A4%B4%E6%8E%92%E5%88%97%EF%BC%9B%E7%8E%B0%E4%BB%B7%E5"
                               "%A4%A7%E4%BA%8E%E7%AD%89%E4%BA%8Eboll%28upper%E5%80%BC%29%EF%BC%9B%E4%BB%8A%E6%97%A5"
                               "%E7%9A%84%E7%AB%9E%E4%BB%B7%E6%B6%A8%E5%B9%85%E5%A4%A7%E4%BA%8E%E7%AD%89%E4%BA%8E0%EF"
                               "%BC%9B%E4%BB%8A%E6%97%A5%E7%9A%84%E9%9B%86%E5%90%88%E7%AB%9E%E4%BB%B7%E8%AF%84%E7%BA"
                               "%A7%E5%8C%85%E5%90%AB%E5%A4%9A%EF%BC%9B%E4%BB%8A%E6%97%A5%E7%9A%84%E7%AB%9E%E4%BB%B7"
                               "%E5%BC%82%E5%8A%A8%E7%B1%BB%E5%9E%8B%E4%B8%8D%E4%B8%BA%E7%A9%BA&querytype=stock",
                        "picurl": "https://img.chkaja.com/7870533166c6773a.jpg"
                    }
                ]
            }
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=4499f04a-88cf-4100-aef3-7528b2a94d67',
            json=json_msg)
    finally:
        print(datetime.datetime.now(), 'A任务结束')
        gc.collect()


# 计算布林带上轨
def bollinger_band(data, window_size=20, num_std_dev=2):
    if len(data) < window_size:
        return None
    # 计算滚动均值
    rolling_mean = statistics.mean(data[-window_size:])
    # 计算滚动标准差
    rolling_std = statistics.stdev(data[-window_size:])
    # 计算布林带上轨
    upper_band = rolling_mean + (rolling_std * num_std_dev)
    return rolling_mean, upper_band


# 判断多头排列
def is_golden_cross(data, short_window=5, mid_window=10, long_window=20):
    if len(data) < long_window:
        return None
    short_ma = statistics.mean(data[-short_window:])
    mid_ma = statistics.mean(data[-mid_window:])
    long_ma = statistics.mean(data[-long_window:])
    # 判定是否满足多头排列条件
    return short_ma >= mid_ma >= long_ma


def get_kline(symbol, t: str):
    if "-USDT" in symbol:
        kline = [list(map(float, sublist)) for sublist in
                 marketDataAPI.get_candlesticks(instId=symbol, bar=t.upper(), limit=20).get('data')[::-1]]
    else:
        kline = [list(map(float, sublist)) for sublist in
                 client.klines(symbol=symbol, interval=t, limit=20)]
    return kline


def rzq_token(symbol, alert, success):
    if symbol in alert:
        success.add(symbol)
        return
    for i in range(10):
        try:
            kline = get_kline(symbol, "1d")
            price_close = kline[-1][4]
            price_vol = kline[-2][4]
            zf = price_close / price_vol - 1
            price_zy = price_close + price_vol * min(0.05, zf * 0.5)
            kline_close = [k[4] for k in kline]
            rolling_mean, upper_band = bollinger_band(kline_close)
            success.add(symbol)
            if (zf >= 0.02 and price_zy > kline[-1][2]
                    and price_close >= max(upper_band, (kline[-2][2] + kline[-2][3]) * 0.51)
                    and is_golden_cross(kline_close)):
                alert.update({symbol: (price_close, zf, price_zy, rolling_mean)})
                return {symbol: (price_close, zf, price_zy, rolling_mean)}
        except:
            time.sleep(1)


def rzq_market(market, symbols, job):
    print(datetime.datetime.now(), f'{market}任务开始', len(symbols))
    alert = alert_all.get(market, {})
    if datetime.datetime.now().hour == 8 and datetime.datetime.now().minute < 15:
        alert.clear()
    success = set()
    alert_m = {}
    thread_pool = ThreadPoolExecutor(max_workers=100)
    futures = [thread_pool.submit(job, symbol, alert, success) for symbol in symbols]
    for future in as_completed(futures):
        if r := future.result():
            alert_m.update(r)
    thread_pool.shutdown()
    try:
        print(market, f"""{len(success)}/{len(symbols)}""")
        if alert_m:
            alert_sort = enumerate(sorted(alert_m, key=lambda x: alert_m[x][1], reverse=True))
            alert_final = []
            for i, j in alert_sort:
                alert_final.append(
                    f'{i + 1}.{j.replace("-USDT", "USDT")[:-4]}\n'
                    f'现价:{alert_m[j][0]}\n涨幅:{alert_m[j][1]}\n止盈:{alert_m[j][2]}\n止损:{alert_m[j][3]}')
            json_msg = {
                "msgtype": "text",
                "text": {'content': f'==={market}===\n' + '\n-------\n'.join(alert_final)}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=4499f04a-88cf-4100-aef3-7528b2a94d67',
                json=json_msg)
        elif not success:
            alert_final = [f"""{len(success)}/{len(symbols)}"""]
            json_msg = {
                "msgtype": "text",
                "text": {'content': f'==={market}===\n' + '\n-------\n'.join(alert_final)}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=4499f04a-88cf-4100-aef3-7528b2a94d67',
                json=json_msg)
    finally:
        print(datetime.datetime.now(), f'{market}任务结束', alert_m, alert)
        gc.collect()


def main():
    # rzq_a()
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
    rzq_market('BN', symbols_bn, rzq_token)
    rzq_market('OKX', symbols_okx, rzq_token)
    # 设置任务调度
    scheduler.add_job(rzq_a, 'cron', hour='09', minute='25', second='00', timezone='Asia/Shanghai')
    scheduler.add_job(rzq_market, 'cron', hour='*', minute='*/15', second='10', timezone='Asia/Shanghai',
                      args=['BN', symbols_bn, rzq_token])
    scheduler.add_job(rzq_market, 'cron', hour='*', minute='*/15', second='10', timezone='Asia/Shanghai',
                      args=['OKX', symbols_okx, rzq_token])
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
    client = Spot()
    marketDataAPI = MarketData.MarketAPI(flag='0', debug=False)
    publicDataAPI = PublicData.PublicAPI(flag='0', debug=False)
    alert_all = {'BN': {}, 'OKX': {}}
    main()
