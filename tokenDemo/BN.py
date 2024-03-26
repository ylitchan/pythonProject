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
# symbols={'SYSUSDT'}
client = Spot()


# print(client.time())
#
# client = Spot(base_url="https://testnet.binance.vision",
#               api_key='1hXMPebjBGCdviw',
#               api_secret='XasQtYcQHOO4S3bADmdzmvI1Oa')
def job():
    alert = []
    for symbol in symbols:
        lines_hour = [[float(i) for i in sub] for sub in client.klines(symbol=symbol, interval="1h", limit=8)[:-1]]
        # 最高量所在索引,价格
        line_vol = max(range(len(lines_hour)), key=lambda x: lines_hour[x][5])
        price = lines_hour[line_vol][4]
        # 最高量之后的索引范围，所爆量
        if 2 < line_vol < 6 and price >= lines_hour[line_vol][1] and price >= lines_hour[line_vol - 1][1]:
            index = range(line_vol + 1, 6)
            vol = lines_hour[line_vol][5]
            stop = False
        else:
            continue
        # 保证当前K线是首根阳K
        for i in index:
            if lines_hour[i][4] > lines_hour[i][1]:
                stop = True
                break
        price = lines_hour[-1][4]
        # 爆量之后缩量真阳K
        if not stop and price > lines_hour[-1][
            1] and price > lines_hour[-2][4] and vol >= lines_hour[-1][5] * 2 and vol >= \
                max(lines_hour[:line_vol], key=lambda x: x[5])[5] * 2:
            # 获取涨幅
            lines_day = [float(sub) for sub in client.klines(symbol=symbol, interval="1d", limit=1)[-1]]
            zf = (lines_day[4] / lines_day[1] - 1) * 100
            print(f'{symbol}\n现价:{price}\n涨幅:{zf}')
            if zf >= 0:
                alert.append((symbol, price, zf, line_vol - 6))
    if alert:
        # 逼空点距离，涨幅降序
        alert = [f'{a[0]}\n现价:{a[1]}\n涨幅:{a[2]}' for a in sorted(alert, key=lambda x: (x[3], x[2]), reverse=True)]
        json = {
            "msgtype": "text",
            "text": {'content': '\n💰💰💰💰💰💰💰\n'.join(alert)}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
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
