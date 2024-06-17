import datetime
import gc
import json
import statistics
import threading
import time

import okx.MarketData as MarketData
import okx.PublicData as PublicData
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from binance.spot import Spot
from jsonpath_ng import parse
from lxml import etree

session = requests.Session()
session.headers = {'Content-Type': 'application/json',
                   'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'}
# 创建BlockingScheduler对象
scheduler = BlockingScheduler()
client = Spot()
marketDataAPI = MarketData.MarketAPI(flag='0', debug=False)
publicDataAPI = PublicData.PublicAPI(flag='0', debug=False)


def rzq_a():
    try:
        print(datetime.datetime.now(), 'A任务开始')
        json = {
            "msgtype": "news",
            "news": {
                "articles": [
                    {
                        "title": "主人，请享用[害羞]",
                        "description": "",
                        "url": "https://www.iwencai.com/unifiedmobile/?q=%E6%98%A8%E6%97%A5%E7%9A%84%E6%94%BE%E5%B7%A8%E9%87%8F%EF%BC%9B%E6%98%A8%E6%97%A5%E7%9A%84%E6%B6%A8%E5%81%9C%EF%BC%9B%E6%98%A8%E6%97%A5%E7%9A%84%E6%94%B6%E7%9B%98%E4%BB%B7%E5%A4%A7%E4%BA%8E%E7%AD%89%E4%BA%8E%E6%98%A8%E6%97%A5%E7%9A%84boll%28upper%E5%80%BC%29%EF%BC%9B%E4%BB%8A%E6%97%A5%E7%9A%84%E7%AB%9E%E4%BB%B7%E6%B6%A8%E5%B9%85%E5%A4%A7%E4%BA%8E%E7%AD%89%E4%BA%8E0%EF%BC%9B%E4%BB%8A%E6%97%A5%E7%9A%84%E9%9B%86%E5%90%88%E7%AB%9E%E4%BB%B7%E8%AF%84%E7%BA%A7%E5%8C%85%E5%90%AB%E5%A4%9A%EF%BC%9B%E4%BB%8A%E6%97%A5%E7%9A%84%E7%AB%9E%E4%BB%B7%E5%BC%82%E5%8A%A8%E7%B1%BB%E5%9E%8B%E4%B8%8D%E4%B8%BA%E7%A9%BA&queryType=stock#/result?question=%E6%98%A8%E6%97%A5%E7%9A%84%E6%94%BE%E5%B7%A8%E9%87%8F%EF%BC%9B%E6%98%A8%E6%97%A5%E7%9A%84%E6%B6%A8%E5%81%9C%EF%BC%9B%E6%98%A8%E6%97%A5%E7%9A%84%E6%94%B6%E7%9B%98%E4%BB%B7%E5%A4%A7%E4%BA%8E%E7%AD%89%E4%BA%8E%E6%98%A8%E6%97%A5%E7%9A%84boll%28upper%E5%80%BC%29%EF%BC%9B%E4%BB%8A%E6%97%A5%E7%9A%84%E7%AB%9E%E4%BB%B7%E6%B6%A8%E5%B9%85%E5%A4%A7%E4%BA%8E%E7%AD%89%E4%BA%8E0%EF%BC%9B%E4%BB%8A%E6%97%A5%E7%9A%84%E9%9B%86%E5%90%88%E7%AB%9E%E4%BB%B7%E8%AF%84%E7%BA%A7%E5%8C%85%E5%90%AB%E5%A4%9A%EF%BC%9B%E4%BB%8A%E6%97%A5%E7%9A%84%E7%AB%9E%E4%BB%B7%E5%BC%82%E5%8A%A8%E7%B1%BB%E5%9E%8B%E4%B8%8D%E4%B8%BA%E7%A9%BA%EF%BC%9B%E6%98%A8%E6%97%A5%E7%9A%84%E6%B6%A8%E5%81%9C%E5%8E%9F%E5%9B%A0%E7%B1%BB%E5%88%AB%E4%B8%8D%E4%B8%BA%E7%A9%BA&queryType=&token=&condition=&short_condition=&sign=1716946468175",
                        "picurl": "https://img.chkaja.com/7870533166c6773a.jpg"
                    }
                ]
            }
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=4499f04a-88cf-4100-aef3-7528b2a94d67',
            json=json)
    finally:
        print(datetime.datetime.now(), 'A任务结束')
        gc.collect()


# 计算布林带上轨
def bollinger_band_upper(data, window_size=20, num_std_dev=2):
    if len(data) < window_size:
        return None
    # 计算滚动均值
    rolling_mean = statistics.mean(data[-window_size:])
    # 计算滚动标准差
    rolling_std = statistics.stdev(data[-window_size:])
    # 计算布林带上轨
    upper_band = rolling_mean + (rolling_std * num_std_dev)
    return upper_band


def rzq_token(symbol, alert, success):
    for i in range(10):
        try:
            if "-USDT" in symbol:
                kline_hour = [list(map(float, sublist)) for sublist in
                              marketDataAPI.get_candlesticks(instId=symbol, bar="4H", limit=22).get('data')[::-1]]
            else:
                kline_hour = [list(map(float, sublist)) for sublist in
                              client.klines(symbol=symbol, interval="4h", limit=22)]
            price_close = kline_hour[-1][4]
            price_vol = kline_hour[-2][4]
            zf = (price_vol / kline_hour[-3][4] - 1) * 100
            # 止盈涨幅6个点，止损亏4个点
            if (zf >= 4 and price_vol * 1.04 > kline_hour[-1][2] and price_close >= price_vol >=
                    bollinger_band_upper([k[4] for k in kline_hour[:21]], 21)
                    and kline_hour[-2][5] >= statistics.mean([k[5] for k in kline_hour[:21]]) * 4):
                alert.append((symbol, price_close, zf, price_vol * 1.06, price_close * 0.96))
            success.add(symbol)
            break
        except Exception:
            time.sleep(2)


def rzq_market(market, symbols, job):
    print(datetime.datetime.now(), f'{market}任务开始', len(symbols))
    alert = []
    success = set()
    # 创建线程列表
    threads = []
    for symbol in symbols:
        # 创建并启动多个线程
        t = threading.Thread(target=job, args=(symbol, alert, success))
        t.start()
        threads.append(t)
        # 等待所有线程完成
    for t in threads:
        t.join()
    try:
        print(market, f"""{len(success)}/{len(symbols)}""")
        if alert:
            alert_sort = enumerate(sorted(alert, key=lambda x: x[2], reverse=True))
            alert.clear()
            for i, j in alert_sort:
                alert.append(
                    f'{i + 1}.{j[0].replace("-USDT", "USDT")[:-4]}\n现价:{j[1]}\n涨幅:{j[2]}\n止盈:{j[3]}\n止损:{j[4]}')
            json = {
                "msgtype": "text",
                "text": {'content': f'==={market}===\n' + '\n-------\n'.join(alert)}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=4499f04a-88cf-4100-aef3-7528b2a94d67',
                json=json)
    finally:
        print(datetime.datetime.now(), f'{market}任务结束', alert)
        gc.collect()


def main():
    rzq_a()
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
    scheduler.add_job(rzq_market, 'cron', hour='*/1', minute='00', second='00', timezone='Asia/Shanghai',
                      args=['BN', symbols_bn, rzq_token])
    scheduler.add_job(rzq_market, 'cron', hour='*/1', minute='00', second='00', timezone='Asia/Shanghai',
                      args=['OKX', symbols_okx, rzq_token])
    # 启动调度器
    scheduler.start()


if __name__ == "__main__":
    main()
