import datetime
import gc
import json
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
                        "title": "会所嫩模领取",
                        "description": "",
                        "url": "https://www.iwencai.com/unifiedwap/result?w=%E6%98%A8%E6%97%A5%E7%88%86%E9%87%8F%E6"
                               "%B6%A8%E5%81%9C%3B%E4%BB%8A%E6%97%A5%E7%AB%9E%E4%BB%B7%E9%AB%98%E5%BC%80%3B%E7%AB%9E"
                               "%E4%BB%B7%E5%BC%82%E5%8A%A8%E8%AF%B4%E6%98%8E%3B%E6%98%A8%E6%97%A5%E6%B6%A8%E5%81%9C"
                               "%E5%8E%9F%E5%9B%A0%E7%B1%BB%E5%88%AB%3B%E9%9B%86%E5%90%88%E7%AB%9E%E4%BB%B7%E8%AF%84"
                               "%E7%BA%A7%E5%8C%85%E5%90%AB%E7%9C%8B%E5%A4%9A%E6%88%96%E8%80%85%E5%81%8F%E5%A4%9A"
                               "&querytype=stock",
                        "picurl": "https://img11.chkaja.com/files/20240402/cf65830bbf07486c.jpg"
                    }
                ]
            }
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=4499f04a-88cf-4100-aef3-7528b2a94d67',
            json=json)
    except Exception as e:
        print(str(e))
    finally:
        print(datetime.datetime.now(), 'A任务结束')
        gc.collect()


def rzq_token(symbol, alert):
    for i in range(10):
        try:
            if "-USDT" in symbol:
                kline_hour = [list(map(float, sublist)) for sublist in
                              marketDataAPI.get_candlesticks(instId=symbol, bar="1Dutc", limit=6).get('data')[::-1]]
            else:
                kline_hour = [list(map(float, sublist)) for sublist in
                              client.klines(symbol=symbol, interval="1d", limit=6)]
            price_close = kline_hour[-1][4]
            if (price_close >= kline_hour[-2][4] >= max(kline_hour[:-2], key=lambda y: y[2])[2]
                    and kline_hour[-2][5] >= max(max(kline_hour[:-2], key=lambda y: y[5])[5] * 4,
                                                 kline_hour[-1][5] * 4)):
                alert.append(
                    (symbol, price_close, (kline_hour[-2][4] / kline_hour[-3][4] - 1) * 100, price_close * 1.04))
            break
        except Exception as e:
            time.sleep(2)


def rzq_market(market, symbols, job):
    print(datetime.datetime.now(), f'{market}任务开始', len(symbols))
    alert = []
    # 创建线程列表
    threads = []
    for symbol in symbols:
        # 创建并启动多个线程
        t = threading.Thread(target=job, args=(symbol, alert))
        t.start()
        threads.append(t)
        # 等待所有线程完成
    for t in threads:
        t.join()
    try:
        if alert:
            alert_sort = enumerate(sorted(alert, key=lambda x: x[2], reverse=True))
            alert.clear()
            for i, j in alert_sort:
                alert.append(f'{i + 1}.{j[0].replace("-USDT", "USDT")[:-4]}\n现价:{j[1]}\n涨幅:{j[2]}\n目标:{j[3]}')
            json = {
                "msgtype": "text",
                "text": {'content': f'==={market}===\n' + '\n-------\n'.join(alert)}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
                json=json)
    except Exception as e:
        print(str(e))
    finally:
        print(datetime.datetime.now(), f'{market}任务结束', alert)
        gc.collect()


def main():
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
        except Exception as e:
            print(('symbols_okx', i))
    rzq_market('BN', symbols_bn, rzq_token)
    rzq_market('OKX', symbols_okx, rzq_token)
    # rzq()
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
