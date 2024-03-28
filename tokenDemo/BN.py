import datetime
import requests
from binance.spot import Spot
from apscheduler.schedulers.blocking import BlockingScheduler

session = requests.Session()
session.headers = {'Content-Type': 'application/json',
                   'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'}
# 创建BlockingScheduler对象
scheduler = BlockingScheduler()

symbols = {'OAXUSDT', 'OOKIUSDT', 'ZILUSDT', 'KAVAUSDT', 'CREAMUSDT', 'EGLDUSDT', 'ZRXUSDT', 'ALCXUSDT', 'IQUSDT',
           'OSMOUSDT', 'CAKEUSDT', 'XVSUSDT', 'ALPHAUSDT', 'IRISUSDT', 'ANKRUSDT', 'LUNAUSDT', 'LITUSDT', 'BONKUSDT',
           'JUPUSDT', 'CYBERUSDT', 'PIVXUSDT', 'UNFIUSDT', 'WOOUSDT', 'ERNUSDT', 'MLNUSDT', 'SUIUSDT', 'VTHOUSDT',
           'KDAUSDT', 'BSWUSDT', 'ARDRUSDT', 'WAXPUSDT', 'BETAUSDT', 'DIAUSDT', 'MOBUSDT', 'CHRUSDT', 'ALICEUSDT',
           'FILUSDT', 'WRXUSDT', 'HIGHUSDT', 'API3USDT', 'POLSUSDT', 'VANRYUSDT', 'JASMYUSDT', 'AAVEUSDT', 'AVAXUSDT',
           'MBOXUSDT', 'RLCUSDT', 'MATICUSDT', 'UMAUSDT', 'STORJUSDT', 'AVAUSDT', 'RVNUSDT', 'BOMEUSDT', 'MOVRUSDT',
           'LINKUSDT', 'OPUSDT', 'CHESSUSDT', 'CTXCUSDT', 'YGGUSDT', 'TRXUSDT', 'XAIUSDT', 'KSMUSDT', 'AEVOUSDT',
           'WINUSDT', 'PNTUSDT', 'ALGOUSDT', 'CKBUSDT', 'QTUMUSDT', 'SLPUSDT', 'INJUSDT', 'WANUSDT', 'FXSUSDT',
           'MDTUSDT', 'BEAMXUSDT', 'NEOUSDT', 'SYNUSDT', 'MKRUSDT', 'POWRUSDT', 'RDNTUSDT', 'ATMUSDT', 'QIUSDT',
           '1INCHUSDT', 'XNOUSDT', 'PHAUSDT', 'USDPUSDT', 'RUNEUSDT', 'BALUSDT', 'HARDUSDT', 'VGXUSDT', 'ARPAUSDT',
           'LRCUSDT', 'GTCUSDT', 'LDOUSDT', 'HBARUSDT', 'TUSDT', 'LINAUSDT', 'USDTBIDR', 'DEGOUSDT', 'VOXELUSDT',
           'AMBUSDT', 'GLMRUSDT', 'OMUSDT', 'STXUSDT', 'BAKEUSDT', 'RNDRUSDT', 'FLUXUSDT', 'GRTUSDT', 'SOLUSDT',
           'REQUSDT', 'PEPEUSDT', 'MANAUSDT', 'OCEANUSDT', 'FDUSDTRY', 'COSUSDT', 'ACHUSDT', 'LQTYUSDT', 'SANDUSDT',
           'USDTPLN', 'RONINUSDT', 'QNTUSDT', 'MEMEUSDT', 'IDUSDT', 'IDEXUSDT', 'PORTOUSDT', 'VITEUSDT', 'WINGUSDT',
           'SUSHIUSDT', 'ZENUSDT', 'STEEMUSDT', 'ACAUSDT', 'BNBUSDT', 'STRKUSDT', 'CVXUSDT', 'WBETHUSDT', 'REIUSDT',
           'LOKAUSDT', 'LTCUSDT', 'DEXEUSDT', 'NULSUSDT', 'DYMUSDT', 'EDUUSDT', 'LPTUSDT', 'ONGUSDT', 'FORTHUSDT',
           'USDTIDRT', 'JSTUSDT', 'KLAYUSDT', 'GASUSDT', 'IOSTUSDT', 'JTOUSDT', 'USTCUSDT', 'BELUSDT', 'GMXUSDT',
           'ENSUSDT', 'ETHFIUSDT', 'FRONTUSDT', 'FLOWUSDT', 'REEFUSDT', 'HOTUSDT', 'MBLUSDT', 'PIXELUSDT', 'ATOMUSDT',
           'USDTBRL', 'DENTUSDT', 'AGIXUSDT', 'BNXUSDT', 'EURUSDT', 'AKROUSDT', 'IOTXUSDT', 'WNXMUSDT', 'CVCUSDT',
           'AIUSDT', 'NKNUSDT', 'ADXUSDT', 'GALAUSDT', 'BNTUSDT', 'BTTCUSDT', 'DOGEUSDT', 'PROMUSDT', 'AGLDUSDT',
           'NFPUSDT', 'DATAUSDT', 'MINAUSDT', 'UNIUSDT', 'VICUSDT', 'IMXUSDT', 'AXSUSDT', 'JOEUSDT', 'COMPUSDT',
           'ARBUSDT', 'KNCUSDT', 'GFTUSDT', 'HIVEUSDT', 'DARUSDT', 'AXLUSDT', 'DUSKUSDT', 'ORDIUSDT', 'DREPUSDT',
           'AEURUSDT', 'METISUSDT', '1000SATSUSDT', 'BIFIUSDT', 'ONTUSDT', 'COTIUSDT', 'SCRTUSDT', 'DASHUSDT',
           'ATAUSDT', 'TRBUSDT', 'LOOMUSDT', 'SYSUSDT', 'TUSDTRY', 'TROYUSDT', 'FUNUSDT', 'AERGOUSDT', 'ALTUSDT',
           'BARUSDT', 'BURGERUSDT', 'C98USDT', 'BICOUSDT', 'BADGERUSDT', 'WAVESUSDT', 'OGUSDT', 'XRPUSDT', 'MAGICUSDT',
           'QUICKUSDT', 'KEYUSDT', 'DCRUSDT', 'COMBOUSDT', 'EPXUSDT', 'ELFUSDT', 'GNOUSDT', 'PAXGUSDT', 'GALUSDT',
           'KP3RUSDT', 'SNXUSDT', 'ARKMUSDT', 'FLOKIUSDT', 'CHZUSDT', 'FIROUSDT', 'USDTUAH', 'LSKUSDT', 'TKOUSDT',
           'TRUUSDT', 'DODOUSDT', 'RIFUSDT', 'GHSTUSDT', 'CRVUSDT', 'OXTUSDT', 'PYTHUSDT', 'TLMUSDT', 'STGUSDT',
           'APEUSDT', 'SNTUSDT', 'ARKUSDT', 'TFUELUSDT', 'WBTCUSDT', 'FORUSDT', 'VIDTUSDT', 'THETAUSDT', 'ASTRUSDT',
           'FETUSDT', 'ASRUSDT', 'PEOPLEUSDT', 'FISUSDT', 'SKLUSDT', 'FTMUSDT', 'SUPERUSDT', 'DOTUSDT', 'XEMUSDT',
           'PORTALUSDT', 'MASKUSDT', 'TUSDUSDT', 'RAREUSDT', 'NEXOUSDT', 'USDTTRY', 'FTTUSDT', 'XECUSDT', 'JUVUSDT',
           'HOOKUSDT', 'PSGUSDT', 'HIFIUSDT', 'DFUSDT', 'SHIBUSDT', 'PERPUSDT', 'RAYUSDT', 'IOTAUSDT', 'APTUSDT',
           'ARUSDT', 'ASTUSDT', 'SXPUSDT', 'XVGUSDT', 'SFPUSDT', 'WIFUSDT', 'CLVUSDT', 'LAZIOUSDT', 'ETHUSDT',
           'DOCKUSDT', 'AUDIOUSDT', 'RADUSDT', 'ILVUSDT', 'EOSUSDT', 'ADAUSDT', 'YFIUSDT', 'LTOUSDT', 'USDTDAI',
           'FLMUSDT', 'ALPACAUSDT', 'PENDLEUSDT', 'FIDAUSDT', 'LEVERUSDT', 'BLZUSDT', 'ICXUSDT', 'MAVUSDT', 'CTKUSDT',
           'USDCUSDT', 'STPTUSDT', 'STMXUSDT', 'USDTRON', 'POLYXUSDT', 'FIOUSDT', 'FDUSDUSDT', 'HFTUSDT', 'PUNDIXUSDT',
           'OMGUSDT', 'GLMUSDT', 'SCUSDT', 'PHBUSDT', 'BANDUSDT', 'GMTUSDT', 'CFXUSDT', 'ONEUSDT', 'BLURUSDT',
           'ORNUSDT', 'CELOUSDT', 'ETCUSDT', 'MDXUSDT', 'PROSUSDT', 'PYRUSDT', 'MANTAUSDT', 'USDTZAR', 'ALPINEUSDT',
           'ROSEUSDT', 'CITYUSDT', 'CTSIUSDT', 'USDTARS', 'OGNUSDT', 'XLMUSDT', 'SPELLUSDT', 'DGBUSDT', 'TWTUSDT',
           'VIBUSDT', 'XTZUSDT', 'PONDUSDT', 'DYDXUSDT', 'CVPUSDT', 'CELRUSDT', 'AUCTIONUSDT', 'BCHUSDT', 'SANTOSUSDT',
           'ACMUSDT', 'NEARUSDT', 'ACEUSDT', 'LUNCUSDT', 'ICPUSDT', 'RENUSDT', 'BONDUSDT', 'TIAUSDT', 'QKCUSDT',
           'VETUSDT', 'RSRUSDT', 'NMRUSDT', 'SSVUSDT', 'WLDUSDT', 'UFTUSDT', 'RPLUSDT', 'PDAUSDT', 'FARMUSDT',
           'UTKUSDT', 'ENJUSDT', 'KMDUSDT', 'AMPUSDT', 'MTLUSDT', 'SEIUSDT', 'BATUSDT', 'SUNUSDT', 'BTCUSDT', 'GNSUSDT',
           'ZECUSDT', 'NTRNUSDT'}
symbols_tvl = {'AGLDUSDT', 'ALPACAUSDT', 'API3USDT', 'ARKMUSDT', 'AUCTIONUSDT', 'AVAUSDT', 'AXLUSDT', 'BAKEUSDT',
               'BANDUSDT', 'BIFIUSDT', 'BLZUSDT', 'C98USDT', 'CELRUSDT', 'CHRUSDT', 'CYBERUSDT', 'DIAUSDT', 'DODOUSDT',
               'FIROUSDT', 'FLUXUSDT', 'FUNUSDT', 'GALUSDT', 'GLMRUSDT', 'GNSUSDT', 'GTCUSDT', 'HARDUSDT', 'HIGHUSDT',
               'IDUSDT', 'JOEUSDT', 'KDAUSDT', 'LOKAUSDT', 'LPTUSDT', 'LQTYUSDT', 'MAGICUSDT', 'MAVUSDT', 'MBOXUSDT',
               'METISUSDT', 'MLNUSDT', 'MOBUSDT', 'OGNUSDT', 'ORDIUSDT', 'PENDLEUSDT', 'PERPUSDT', 'POLSUSDT', 'QIUSDT',
               'RAYUSDT', 'RDNTUSDT', 'RSRUSDT', 'SCRTUSDT', 'SPELLUSDT', 'SSVUSDT', 'STGUSDT', 'STORJUSDT',
               'SUSHIUSDT', 'SYNUSDT', 'TKOUSDT', 'UMAUSDT', 'VOXELUSDT', 'WAVESUSDT', 'WAXPUSDT', 'XVGUSDT', 'XVSUSDT',
               'YGGUSDT', 'ZRXUSDT'}
client = Spot()


# print(client.time())
#
# client = Spot(base_url="https://testnet.binance.vision",
#               api_key='1hXMPebjBGCdviw',
#               api_secret='XasQtYcQHOO4S3bADmdzmvI1Oa')
def job():
    print(datetime.datetime.now())
    alert = []
    alert_tvl = []
    alert_boom = []
    for symbol in symbols:
        kline_hour = [[float(i) for i in sub] for sub in client.klines(symbol=symbol, interval="1h", limit=8)[:-1]]
        # 最高量所在索引,价格
        kline_vol = max(range(len(kline_hour)), key=lambda x: kline_hour[x][5])
        price_vol = kline_hour[kline_vol][4]
        price = kline_hour[-1][4]
        stop = False
        # 最高量之后的索引范围，所爆量
        if 2 < kline_vol < 6:  # and price >= kline_hour[kline_vol][1] and price >= kline_hour[kline_vol - 1][1]:
            vol = kline_hour[kline_vol][5]
            index_range = range(kline_vol + 1, 6)
            # 爆量阴K,没有反包
            if kline_hour[kline_vol][1] > price_vol > price:
                stop = True
        else:
            continue
        # 当前为爆量后缩量真阳K
        if not stop and price > kline_hour[-1][
            1] and price > kline_hour[-2][4] and vol >= kline_hour[-1][5] * 2 and vol >= \
                max(kline_hour[:kline_vol], key=lambda x: x[5])[5] * 2:
            # 爆量之后阳K数量
            boom = len(list(filter(lambda x: x >= 0, [kline_hour[i][4] - kline_hour[i][1] for i in index_range])))
            kline_distance = 6 - kline_vol
            # 获取涨幅
            kline_day = [float(sub) for sub in client.klines(symbol=symbol, interval="1d", limit=1)[-1]]
            zf = (kline_day[4] / kline_day[1] - 1) * 100
            if symbol in symbols_tvl:
                alert_tvl.append((symbol, price, zf, boom - kline_distance, -boom))
            # if boom == len(index_range):
            #     alert_boom.append((symbol, price, zf, boom - kline_distance, -boom))
            # else:
            alert.append((symbol, price, zf, boom - kline_distance, -boom))
    # if alert_boom:
    #     alert_boom = [f'{a[0]}\n现价:{a[1]}\n涨幅:{a[2]}' for a in
    #                   sorted(alert_boom, key=lambda x: (x[3], x[4],x[2]), reverse=True)]
    #     json = {
    #         "msgtype": "text",
    #         "text": {'content': '\n💰💰💰💰💰💰💰\n'.join(alert_boom)}
    #     }
    #     session.post(
    #         url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=2caca472-4893-490d-aa1b-76e69f4e9b3c',
    #         json=json)
    if alert:
        alert = [f'{a[0]}\n现价:{a[1]}\n涨幅:{a[2]}' for a in
                 sorted(alert, key=lambda x: (x[3], x[4], x[2]), reverse=True)]
        json = {
            "msgtype": "text",
            "text": {'content': '\n💰💰💰💰💰💰💰\n'.join(alert)}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
            json=json)
    if alert_tvl:
        alert_tvl = [f'{a[0]}\n现价:{a[1]}\n涨幅:{a[2]}' for a in
                     sorted(alert_tvl, key=lambda x: (x[3], x[4], x[2]), reverse=True)]
        json = {
            "msgtype": "text",
            "text": {'content': '\n💰💰💰💰💰💰💰\n'.join(alert_tvl)}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=bb15fa90-dee0-4463-896d-2acf26619eaf',
            json=json)


if __name__ == "__main__":
    job()
    # 设置任务调度
    scheduler.add_job(job, 'cron', minute='00', second='10')

    # 启动调度器
    scheduler.start()
# # Get account information
# client.new_order('ETHUSDT', "BUY", "MARKET", quantity=1)
# print(client.account())
