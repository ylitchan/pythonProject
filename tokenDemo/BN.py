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
#               api_key='1hXMPebjBGCdviwi0hXiUvgoakhVVK54BNxFk5QJ7quopqjoY8z2iNWcDD9U94Sp',
#               api_secret='XasQtYcQHOO4S3bADmdzmvI1Oacdlz5a6RjlBa25EqunSOkPTcxdzFJRojTd4MEz')
def job():
    for symbol in symbols:
        print(symbol)
        lines = [[float(i) for i in sub] for sub in client.klines(symbol, "1h", limit=7)]
        # 最高量所在索引
        line_vol = max(range(len(lines)), key=lambda x: lines[x][5])
        price = lines[line_vol][4]
        # 最高量之后的索引范围
        if 2 < line_vol < 6 and price >= lines[line_vol][1] and price >= lines[line_vol - 1][1]:
            index = range(line_vol + 1, 6)
            vol = lines[line_vol][5]
            stop = False
        else:
            continue
        # 保证当前K线是首根阳K
        for i in index:
            if lines[i][4] > lines[i][1]:
                stop = True
                break
        price = lines[-1][4]
        # 爆量之后缩量真阳K
        if not stop and price > lines[-1][
            1] and price > lines[-2][4] and vol >= lines[-1][5] * 2 and vol >= \
                max(lines[:line_vol], key=lambda x: x[5])[5] * 2:
            print(f'{symbol}\n现价:{price}')
            json = {
                "msgtype": "text",
                "text": {'content': f'{symbol}\n现价:{price}'}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
                json=json)


if __name__ == "__main__":
    # job()
    # 设置任务调度
    scheduler.add_job(job, 'cron', minute='55')

    # 启动调度器
    scheduler.start()
# # Get account information
# client.new_order('ETHUSDT', "BUY", "MARKET", quantity=1)
# print(client.account())
