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
           'FIDAUSDT', 'DUSKUSDT', 'MANAUSDT', 'AUCTIONUSDT', 'APTUSDT', 'ACEUSDT', 'ALPINEUSDT', 'XRPUSDT'}
client = Spot(api_key='A19rSNSOEbZqeQrKaV1wyoyhuDOFomARNu8omNQaII3Iv1DvYorfN5OeVlTv198A',
              api_secret='fF6yzKflVZNaDbjYUvh2nyc5aMgzSgst8GnxF3hixE9UKwKnjWVxOfg7gipqTztD')


def job():
    print(datetime.datetime.now(), '任务开始')
    symbols_asset = {s['asset'] for s in client.user_asset(recvWindow=60000)}
    alert_b = []
    alert_boom = []
    for symbol in symbols:
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
                        (symbol, price_close, zf, symbol[:-4] in symbols_asset))
                elif kline_vol < 6 and price_close >= price_close_vol and vol >= \
                        kline_hour[-1][5] * 2:
                    alert_b.append((symbol, price_close, zf, symbol[:-4] in symbols_asset))
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
        alert_boom = [f'{i + 1}.{j[0][:-4]}\n现价:{j[1]}\n涨幅:{j[2]}\n持仓:{j[3]}' for i, j in
                      enumerate(sorted(alert_boom, key=lambda x: x[2], reverse=True))]
        alert_b = [f'{i + 1}.{j[0][:-4]}\n现价:{j[1]}\n涨幅:{j[2]}\n持仓:{j[3]}' for i, j in
                   enumerate(sorted(alert_b, key=lambda x: x[2], reverse=True))]
        json = {
            "msgtype": "text",
            "text": {'content': f'===爆===\n' + '\n-------\n'.join(
                alert_boom) + f'\n===B===\n' + '\n-------\n'.join(alert_b)}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=4499f04a-88cf-4100-aef3-7528b2a94d67',
            json=json)
    print(datetime.datetime.now(), '任务结束')
    gc.collect()


if __name__ == "__main__":
    job()
    # 设置任务调度
    scheduler.add_job(job, 'cron', minute='00', second='03')
    # 启动调度器
    scheduler.start()
