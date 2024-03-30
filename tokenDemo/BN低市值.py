import datetime
import gc
import requests
from binance.spot import Spot
from apscheduler.schedulers.blocking import BlockingScheduler

session = requests.Session()
session.headers = {'Content-Type': 'application/json',
                   'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'}
# 创建BlockingScheduler对象
scheduler = BlockingScheduler()
symbols_tvl = {'CELRUSDT', 'DIAUSDT', 'TKOUSDT', 'HIGHUSDT', 'API3USDT', 'JOEUSDT', 'AXLUSDT', 'SSVUSDT', 'METISUSDT',
               'CHRUSDT', 'SUSHIUSDT', 'AGLDUSDT', 'VOXELUSDT', 'GTCUSDT', 'FUNUSDT', 'MLNUSDT', 'XVGUSDT', 'ARKMUSDT',
               'PENDLEUSDT', 'AVAUSDT', 'DODOUSDT', 'MOBUSDT', 'SCRTUSDT', 'MAVUSDT', 'ORDIUSDT', 'STORJUSDT',
               'FIROUSDT', 'KDAUSDT', 'SYNUSDT', 'AUCTIONUSDT', 'LPTUSDT', 'ZRXUSDT', 'OGNUSDT', 'CYBERUSDT',
               'GLMRUSDT', 'UMAUSDT', 'POLSUSDT', 'XVSUSDT', 'LOKAUSDT', 'WAVESUSDT', 'MBOXUSDT', 'FLUXUSDT', 'STGUSDT',
               'HARDUSDT', 'WAXPUSDT', 'ALPACAUSDT', 'GALUSDT', 'C98USDT', 'QIUSDT', 'GNSUSDT', 'PERPUSDT', 'RAYUSDT',
               'RSRUSDT', 'BLZUSDT', 'BAKEUSDT', 'BIFIUSDT', 'YGGUSDT', 'SPELLUSDT', 'BANDUSDT', 'LQTYUSDT', 'IDUSDT',
               'RDNTUSDT', 'MAGICUSDT'}
client = Spot()


def job():
    print(datetime.datetime.now(), '任务开始')
    alert_b = []
    alert_boom = []
    for symbol in symbols_tvl:
        try:
            kline_hour = [[float(i) for i in sub] for sub in client.klines(symbol=symbol, interval="1h", limit=8)[:-1]]
            price_close = kline_hour[-1][4]
            price_open = kline_hour[-1][1]
            # 最高量所在索引
            kline_vol = max(range(len(kline_hour)), key=lambda x: kline_hour[x][5])
            price_close_vol = kline_hour[kline_vol][4]
            vol = kline_hour[kline_vol][5]
            if kline_vol > 2 and price_close >= price_open and price_close_vol >= \
                    max(kline_hour[:kline_vol], key=lambda x: x[2])[2] and vol >= \
                    max(kline_hour[:kline_vol], key=lambda x: x[5])[5] * 2:
                zf = (price_close_vol / kline_hour[kline_vol - 1][4] - 1) * 100
                if kline_vol == 6:
                    alert_boom.append(
                        (symbol[:-4], price_close, zf))
                elif kline_vol < 6 and price_close >= price_close_vol and vol >= \
                        kline_hour[-1][5] * 2:
                    alert_b.append((symbol[:-4], price_close, zf))
                else:
                    continue
            else:
                continue
        except Exception as e:
            print(str(e))
            continue
        else:
            pass
    if alert_boom + alert_b:
        alert_boom = [f'{i + 1}.{j[0]}\n现价:{j[1]}\n涨幅:{j[2]}' for i, j in
                      enumerate(sorted(alert_boom, key=lambda x: x[-1], reverse=True))]
        alert_b = [f'{i + 1}.{j[0]}\n现价:{j[1]}\n涨幅:{j[2]}' for i, j in
                   enumerate(sorted(alert_b, key=lambda x: x[-1], reverse=True))]
        json = {
            "msgtype": "text",
            "text": {'content': f'===爆===\n' + '\n-------\n'.join(
                alert_boom) + f'\n===逼===\n' + '\n-------\n'.join(alert_b)}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=2caca472-4893-490d-aa1b-76e69f4e9b3c',
            json=json)
    print(datetime.datetime.now(), '任务结束')
    gc.collect()


if __name__ == "__main__":
    job()
    # 设置任务调度
    scheduler.add_job(job, 'cron', minute='00', second='3')
    # 启动调度器
    scheduler.start()
