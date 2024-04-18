import datetime
import gc
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from binance.spot import Spot

session = requests.Session()
session.headers = {'Content-Type': 'application/json',
                   'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'}
# 创建BlockingScheduler对象
scheduler_BN = BlockingScheduler()
scheduler_A = BackgroundScheduler()
symbols = {'PORTALUSDT', 'PHBUSDT', 'PNTUSDT', 'ADXUSDT', 'APEUSDT', 'SUPERUSDT', 'NEOUSDT', 'RUNEUSDT', 'XLMUSDT',
           'IQUSDT', 'UNIUSDT', 'RAREUSDT', 'FLOKIUSDT', 'ETHUSDT', 'UFTUSDT', 'HIGHUSDT', 'POLYXUSDT', 'GLMUSDT',
           'EPXUSDT', 'DARUSDT', 'DOTUSDT', 'VETUSDT', 'SCUSDT', 'ANKRUSDT', 'TLMUSDT', 'STGUSDT', 'OMGUSDT', 'SXPUSDT',
           '1INCHUSDT', 'DYMUSDT', 'BEAMXUSDT', 'ERNUSDT', 'DOCKUSDT', 'TUSDT', 'CYBERUSDT', 'CREAMUSDT', 'SANTOSUSDT',
           'BALUSDT', 'RDNTUSDT', 'AUDIOUSDT', 'NMRUSDT', 'HFTUSDT', 'JUPUSDT', 'WANUSDT', 'VICUSDT', 'BLZUSDT',
           'FARMUSDT', 'LTCUSDT', 'PROSUSDT', 'ARKUSDT', 'MDTUSDT', 'VIBUSDT', 'FTTUSDT', 'XEMUSDT', 'FLMUSDT',
           'RLCUSDT', 'GNSUSDT', 'EURUSDT', 'REQUSDT', 'TRBUSDT', 'TFUELUSDT', 'CITYUSDT', 'RIFUSDT', 'REIUSDT',
           'WIFUSDT', 'PERPUSDT', 'SYNUSDT', 'CRVUSDT', 'WLDUSDT', 'MBOXUSDT', 'STEEMUSDT', 'ATMUSDT', 'POLSUSDT',
           'SHIBUSDT', 'ORNUSDT', 'LAZIOUSDT', 'MEMEUSDT', 'STMXUSDT', 'ZILUSDT', 'HIVEUSDT', 'VTHOUSDT', 'TIAUSDT',
           'ACAUSDT', 'AERGOUSDT', 'VGXUSDT', 'SLPUSDT', 'BNXUSDT', 'PAXGUSDT', 'QNTUSDT', 'MBLUSDT', 'CVXUSDT',
           'COTIUSDT', 'EGLDUSDT', 'RENUSDT', 'CTXCUSDT', 'WBTCUSDT', 'IDEXUSDT', 'OAXUSDT', 'PEOPLEUSDT', 'GMTUSDT',
           'ENJUSDT', 'AEURUSDT', 'LSKUSDT', 'OCEANUSDT', 'CELOUSDT', 'OGNUSDT', 'HOOKUSDT', 'IDUSDT', 'FORTHUSDT',
           'FXSUSDT', 'BTCUSDT', 'DOGEUSDT', 'WNXMUSDT', 'LINKUSDT', 'QUICKUSDT', 'WINUSDT', 'ICXUSDT', 'DYDXUSDT',
           'PROMUSDT', 'CTSIUSDT', 'AIUSDT', 'FLOWUSDT', 'PONDUSDT', 'CELRUSDT', 'GMXUSDT', 'XNOUSDT', 'ONEUSDT',
           'WINGUSDT', 'SUIUSDT', 'OMUSDT', 'STRKUSDT', 'DGBUSDT', 'ETHFIUSDT', 'MAVUSDT', 'THETAUSDT', 'FLUXUSDT',
           'RSRUSDT', 'BARUSDT', 'ILVUSDT', 'BLURUSDT', 'BTTCUSDT', 'ELFUSDT', 'SNTUSDT', 'ICPUSDT', 'HIFIUSDT',
           'ALPHAUSDT', 'ATOMUSDT', 'OSMOUSDT', 'KLAYUSDT', 'NEARUSDT', 'WRXUSDT', '1000SATSUSDT', 'GALAUSDT',
           'ARBUSDT', 'TROYUSDT', 'KAVAUSDT', 'BNBUSDT', 'BONDUSDT', 'NULSUSDT', 'AXSUSDT', 'RAYUSDT', 'JTOUSDT',
           'TRXUSDT', 'KNCUSDT', 'PIVXUSDT', 'JSTUSDT', 'SSVUSDT', 'GFTUSDT', 'VIDTUSDT', 'MLNUSDT', 'JASMYUSDT',
           'BIFIUSDT', 'DCRUSDT', 'MKRUSDT', 'BICOUSDT', 'AMBUSDT', 'UNFIUSDT', 'UMAUSDT', 'ARPAUSDT', 'LDOUSDT',
           'CFXUSDT', 'FETUSDT', 'ARDRUSDT', 'WAVESUSDT', 'LUNCUSDT', 'LOOMUSDT', 'KDAUSDT', 'STORJUSDT', 'BOMEUSDT',
           'ATAUSDT', 'FDUSDUSDT', 'SANDUSDT', 'FTMUSDT', 'BETAUSDT', 'PDAUSDT', 'PENDLEUSDT', 'BONKUSDT', 'CHZUSDT',
           'ASTRUSDT', 'SFPUSDT', 'AEVOUSDT', 'GASUSDT', 'LUNAUSDT', 'RONINUSDT', 'PSGUSDT', 'DFUSDT', 'AGLDUSDT',
           'FUNUSDT', 'TWTUSDT', 'SOLUSDT', 'ZENUSDT', 'FIROUSDT', 'HARDUSDT', 'USTCUSDT', 'JOEUSDT', 'MTLUSDT',
           'METISUSDT', 'STPTUSDT', 'KEYUSDT', 'LPTUSDT', 'RADUSDT', 'QKCUSDT', 'WBETHUSDT', 'YGGUSDT', 'BAKEUSDT',
           'GALUSDT', 'NFPUSDT', 'XAIUSDT', 'AKROUSDT', 'BSWUSDT', 'ALCXUSDT', 'INJUSDT', 'ONGUSDT', 'VITEUSDT',
           'FIOUSDT', 'PYRUSDT', 'SUNUSDT', 'STXUSDT', 'IOTAUSDT', 'PYTHUSDT', 'COMPUSDT', 'IOSTUSDT', 'SCRTUSDT',
           'ORDIUSDT', 'TUSDUSDT', 'ALPACAUSDT', 'BATUSDT', 'GRTUSDT', 'AVAXUSDT', 'EOSUSDT', 'FORUSDT', 'AGIXUSDT',
           'NTRNUSDT', 'BCHUSDT', 'CVCUSDT', 'ETCUSDT', 'HBARUSDT', 'COMBOUSDT', 'CHRUSDT', 'ADAUSDT', 'IOTXUSDT',
           'DASHUSDT', 'SPELLUSDT', 'DEXEUSDT', 'CKBUSDT', 'ALTUSDT', 'CHESSUSDT', 'LITUSDT', 'RVNUSDT', 'RNDRUSDT',
           'FISUSDT', 'RPLUSDT', 'CTKUSDT', 'C98USDT', 'KP3RUSDT', 'DODOUSDT', 'ASRUSDT', 'SKLUSDT', 'KMDUSDT',
           'USDPUSDT', 'VANRYUSDT', 'OXTUSDT', 'CLVUSDT', 'SUSHIUSDT', 'MDXUSDT', 'OOKIUSDT', 'LTOUSDT', 'API3USDT',
           'ACHUSDT', 'WOOUSDT', 'ENSUSDT', 'DEGOUSDT', 'MANTAUSDT', 'ARKMUSDT', 'TKOUSDT', 'CAKEUSDT', 'BADGERUSDT',
           'XTZUSDT', 'AXLUSDT', 'SEIUSDT', 'PEPEUSDT', 'YFIUSDT', 'QTUMUSDT', 'LQTYUSDT', 'ARUSDT', 'TRUUSDT',
           'BNTUSDT', 'GNOUSDT', 'POWRUSDT', 'PUNDIXUSDT', 'JUVUSDT', 'KSMUSDT', 'LEVERUSDT', 'COSUSDT', 'DATAUSDT',
           'XVSUSDT', 'LRCUSDT', 'EDUUSDT', 'PORTOUSDT', 'FRONTUSDT', 'OPUSDT', 'HOTUSDT', 'OGUSDT', 'MASKUSDT',
           'DENTUSDT', 'MAGICUSDT', 'CVPUSDT', 'BANDUSDT', 'MATICUSDT', 'GLMRUSDT', 'LOKAUSDT', 'IRISUSDT', 'IMXUSDT',
           'GHSTUSDT', 'ACMUSDT', 'LINAUSDT', 'AAVEUSDT', 'ALICEUSDT', 'DREPUSDT', 'PIXELUSDT', 'SYSUSDT', 'MOVRUSDT',
           'AMPUSDT', 'XVGUSDT', 'GTCUSDT', 'ASTUSDT', 'NKNUSDT', 'BURGERUSDT', 'NEXOUSDT', 'VOXELUSDT', 'XECUSDT',
           'MOBUSDT', 'QIUSDT', 'BELUSDT', 'WAXPUSDT', 'ROSEUSDT', 'ZECUSDT', 'ALGOUSDT', 'USDCUSDT', 'FILUSDT',
           'AVAUSDT', 'REEFUSDT', 'PHAUSDT', 'MINAUSDT', 'ZRXUSDT', 'ONTUSDT', 'DIAUSDT', 'SNXUSDT', 'UTKUSDT',
           'FIDAUSDT', 'DUSKUSDT', 'MANAUSDT', 'AUCTIONUSDT', 'APTUSDT', 'ACEUSDT', 'ALPINEUSDT', 'XRPUSDT', 'TNSRUSDT',
           'WUSDT', 'ENAUSDT'}
symbols_tvl = {'CELRUSDT', 'DIAUSDT', 'TKOUSDT', 'HIGHUSDT', 'API3USDT', 'JOEUSDT', 'AXLUSDT', 'SSVUSDT', 'METISUSDT',
               'CHRUSDT', 'SUSHIUSDT', 'VOXELUSDT', 'GTCUSDT', 'FUNUSDT', 'MLNUSDT', 'XVGUSDT', 'ARKMUSDT',
               'PENDLEUSDT', 'AVAUSDT', 'MOBUSDT', 'SCRTUSDT', 'MAVUSDT', 'ORDIUSDT', 'STORJUSDT',
               'FIROUSDT', 'KDAUSDT', 'SYNUSDT', 'LPTUSDT', 'ZRXUSDT', 'OGNUSDT', 'CYBERUSDT',
               'GLMRUSDT', 'UMAUSDT', 'POLSUSDT', 'XVSUSDT', 'LOKAUSDT', 'MBOXUSDT', 'FLUXUSDT', 'STGUSDT',
               'HARDUSDT', 'WAXPUSDT', 'ALPACAUSDT', 'GALUSDT', 'QIUSDT', 'GNSUSDT', 'PERPUSDT', 'RAYUSDT',
               'RSRUSDT', 'BLZUSDT', 'BAKEUSDT', 'BIFIUSDT', 'SPELLUSDT', 'BANDUSDT', 'LQTYUSDT', 'IDUSDT',
               'RDNTUSDT', 'MAGICUSDT'}
symbols_dwf = {'DODOUSDT', 'AUCTIONUSDT', 'WAVESUSDT', 'YGGUSDT', 'AGLDUSDT', 'C98USDT'}
client = Spot(api_key='A19rSNSOEbZqeQrKaV1wyoyhuDOFomARNu8omNQaII3Iv1DvYorfN5OeVlTv198A',
              api_secret='fF6yzKflVZNaDbjYUvh2nyc5aMgzSgst8GnxF3hixE9UKwKnjWVxOfg7gipqTztD')


def rzq():
    try:
        print(datetime.datetime.now(), 'A任务开始')
        json = {
            "msgtype": "news",
            "news": {
                "articles": [
                    {
                        "title": "会所嫩模领取",
                        "description": "",
                        "url": "https://www.iwencai.com/unifiedwap/result?w=%E6%98%A8%E6%97%A5%E7%88%86%E9%87%8F%E6%B6%A8%E5%81%9C%3B%E4%BB%8A%E6%97%A5%E9%AB%98%E5%BC%80%3B%E7%AB%9E%E4%BB%B7%E5%BC%82%E5%8A%A8%E8%AF%B4%E6%98%8E%3B%E6%B6%A8%E5%81%9C%E5%8E%9F%E5%9B%A0%E7%B1%BB%E5%88%AB%3B%E9%9B%86%E5%90%88%E7%AB%9E%E4%BB%B7%E8%AF%84%E7%BA%A7&querytype=stock",
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


def job():
    try:
        print(datetime.datetime.now(), 'BN任务开始')
        symbols_asset = {s['asset'] for s in client.user_asset()}
    except Exception as e:
        symbols_asset = set()
        print(str(e))
    alert_b = []
    alert_b_else = []
    alert_tvl = []
    alert_dwf = []
    for symbol in symbols:
        try:
            kline_hour = [[float(i) for i in sub] for sub in client.klines(symbol=symbol, interval="1h", limit=8)[:-1]]
            price_close = kline_hour[-1][4]
            price_open = kline_hour[-1][1]
            if price_close >= price_open:
                # 第一个倍量所在索引
                kline_vol = next(filter(
                    lambda x: kline_hour[x][4] / kline_hour[x - 1][4] >= 1.0299 and price_close >= kline_hour[x][
                        4] >= max(kline_hour[:x], key=lambda y: y[2])[2] and kline_hour[x][5] >= max(
                        max(kline_hour[:x], key=lambda y: y[5])[5], kline_hour[-1][5]) * 2, range(3, 6)), None)
                if kline_vol:
                    cc = symbol[:-4] in symbols_asset
                    alert_b.append(
                        (symbol, price_close, (kline_hour[kline_vol][4] / kline_hour[kline_vol - 1][4] - 1) * 100, cc,
                         price_close * 1.0333687020354))
                else:
                    continue
            else:
                continue
        except Exception as e:
            print(str(e))
            continue
    try:
        if alert_b:
            alert_b_sort = enumerate(sorted(alert_b, key=lambda x: x[2], reverse=True))
            alert_b.clear()
            for i, j in alert_b_sort:
                alert_b.append(f'{i + 1}.{j[0][:-4]}\n现价:{j[1]}\n涨幅:{j[2]}\n持仓:{j[3]}\n目标:{j[4]}')
                if j[0] in symbols_tvl:
                    alert_tvl.append(f'{i + 1}.{j[0][:-4]}\n现价:{j[1]}\n涨幅:{j[2]}')
                elif j[0] in symbols_dwf:
                    alert_dwf.append(f'{i + 1}.{j[0][:-4]}\n现价:{j[1]}\n涨幅:{j[2]}')
                else:
                    alert_b_else.append(f'{i + 1}.{j[0][:-4]}\n现价:{j[1]}\n涨幅:{j[2]}')
            json = {
                "msgtype": "text",
                "text": {'content': f'===小步快跑===\n' + '\n-------\n'.join(alert_b)}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=4499f04a-88cf-4100-aef3-7528b2a94d67',
                json=json)
            json = {
                "msgtype": "text",
                "text": {'content': f'===低市值===\n' + '\n-------\n'.join(
                    alert_tvl) + f'\n===DWF===\n' + '\n-------\n'.join(
                    alert_dwf) + f'\n===其他===\n' + '\n-------\n'.join(
                    alert_b_else)}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
                json=json)
    except Exception as e:
        print(str(e))
    finally:
        print(datetime.datetime.now(), 'BN任务结束')
        gc.collect()


if __name__ == "__main__":
    rzq()
    job()
    # 设置任务调度
    scheduler_A.add_job(rzq, 'cron', hour='09', minute='25', second='00', day_of_week='mon-fri',
                        timezone='Asia/Shanghai')
    scheduler_BN.add_job(job, 'cron', minute='00', second='03', timezone='Asia/Shanghai')
    # 启动调度器
    scheduler_A.start()
    scheduler_BN.start()
