import datetime
import gc
import json
import re
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


def find_continuous_subsequences(nums, direction):
    n = len(nums)
    # 临时存储当前递减的子序列
    current_subseq = []
    if direction:
        for i in range(n):
            # 如果当前子序列为空或递减
            if not current_subseq or nums[i] > current_subseq[-1]:
                current_subseq.append(nums[i])
            else:
                ii, kk = find_continuous_subsequences(nums[i - 1:], 0)
                kk_asc = kk[:max(8 - len(current_subseq), 0)][::-1]
                return n - ii - i + len(kk) - len(kk_asc), n - i, kk_asc
        return 0, n - 1, []
    else:
        for i in range(n):
            # 如果当前子序列为空或递减
            if (  # nums[i] >= statistics.mean(nums[i:i + 7]) and
                    nums[i] < nums[i - 1] if i > 0 else True):
                current_subseq.append(nums[i])
            else:
                return i - 1, current_subseq
        return n - 1, current_subseq


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
        success.add(symbol)
        if symbol == 'ETHUSDT' and kline[-1][4] <= 3000:
            alert.update({symbol: (kline[-1][4], 0, 100, 3000)})
            return {symbol: (kline[-1][4], 0, 100, 3000)}
        if kline[-1][4] <= kline[-1][1]:
            return
        index_d = 0
        for i, k in enumerate(kline[::-1]):
            if k[4] <= k[1]:
                index_d = i
                break
        if not index_d:
            return
        kline_close = [k[4] for k in kline]
        index_s, index_e, kline_close_asc = find_continuous_subsequences(kline_close[::-1][index_d:], 1)
        if kline[index_s][4] <= kline[index_s][1]:
            index_s += 1
            kline_close_asc = kline_close_asc[1:]
        price_close = kline[-1][4]
        price_low = min([k[4] for k in kline[index_e + 1:-index_d]])
        if kline[index_e][5] < kline[index_e + 1][5] * 2 or price_low < kline[index_e][1] or kline[-2][
            2] > price_close:  # price_high > price_close or kline[-2][4] >= price_high:
            return
        max_decimal = max(map(get_max_decimal_places, map(str, kline_close)))
        price_vol = kline[-index_d - 1][4]
        zf = round((kline[-2][4] / kline[index_s][1] - 1) * 100, 2)
        zf_m = zf / (len(kline) - 1 - index_s)
        price_zy = round(kline[-2][4] + kline[-2][4] * zf_m / 100, max_decimal)
        expectation = round((price_zy / kline[-2][2] - 1) * 100, 2)
        if expectation < 0:
            price_zy = round(kline[-2][2] + kline[-2][2] * abs(expectation) / 100, max_decimal)
        if 1 or price_zy > kline[-1][2]:
            alert.update({symbol: (price_close, zf, expectation, price_zy)})
            return {symbol: (price_close, zf, expectation, price_zy)}
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
            alert_sort = enumerate(sorted(alert, key=lambda x: alert[x][2], reverse=True))
            for i, j in alert_sort:
                if j not in alert_m:
                    continue
                if 'USDT' in j:
                    alert_final.append(
                        f'{i + 1}.{j.replace("-USDT", "USDT")[:-4]}\n'
                        f'现价:{alert_m[j][0]}\n涨幅:{alert_m[j][1]}\n预期:{alert_m[j][2]}\n止盈:{alert_m[j][3]}')
                else:
                    alert_final.append(
                        f'{i + 1}.{j}\n现价:{alert_m[j][0]}\n涨幅:{alert_m[j][1]}\n预期:{alert_m[j][2]}\n止盈:{alert_m[j][3]}')
            json_msg = {
                "msgtype": "text",
                "text": {'content': f'==={market}{len(alert)}===\n' + '\n-------\n'.join(alert_final)}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
                json=json_msg)
        elif not success and symbols:
            alert_final = [f"""{len(success)}/{len(symbols)}"""]
            json_msg = {
                "msgtype": "text",
                "text": {'content': f'==={market}{len(alert)}===\n' + '\n-------\n'.join(alert_final)}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
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
                       'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
                       'Cookie': "theme=dark; bnc-uuid=6d9f05ed-c1fb-4c36-a14e-f7b2cbbfd719; source=referral; campaign=www.binance.com; BNC_FV_KEY=33a30f78e2f0a7edae1b1049555413b76766234f; se_gd=hsNGlAhBbQGEAoVMECw4gZZUBA1IbBWW1sUdYUEV1FWUAUlNWUBR1; se_gsd=fycgLB1hNSUkCSABJQgiChArDhQRDgFSU1lFUFRSUlFQElNT1; BNC-Location=BINANCE; pl-id=491077510; OptanonAlertBoxClosed=2024-03-13T06:32:22.156Z; userPreferredCurrency=USD_USD; fiat-prefer-currency=CNY; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22491077510%22%2C%22first_id%22%3A%2218e31a6fe0b1294-09171b521a4468-7e56547f-1327104-18e31a6fe0c1a89%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMThlMzFhNmZlMGIxMjk0LTA5MTcxYjUyMWE0NDY4LTdlNTY1NDdmLTEzMjcxMDQtMThlMzFhNmZlMGMxYTg5IiwiJGlkZW50aXR5X2xvZ2luX2lkIjoiNDkxMDc3NTEwIn0%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22491077510%22%7D%2C%22%24device_id%22%3A%2218e31a6fe0b1294-09171b521a4468-7e56547f-1327104-18e31a6fe0c1a89%22%7D; changeBasisTimeZone=0; futures-layout=pro; OptanonConsent=isGpcEnabled=0&datestamp=Tue+Apr+23+2024+15%3A29%3A39+GMT%2B0800+(%E4%B8%AD%E5%9B%BD%E6%A0%87%E5%87%86%E6%97%B6%E9%97%B4)&version=202402.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=0440cd45-f4e5-4c30-a2b9-85508e54fa53&interactionCount=1&landingPath=NotLandingPage&groups=C0001%3A1%2CC0003%3A1%2CC0004%3A1%2CC0002%3A1&geolocation=SG%3B&AwaitingReconsent=false&isAnonUser=1; __BNC_USER_DEVICE_ID__={\"635f2d77fe06ed3429c74e15eb59b4f8\":{\"date\":1710221906481,\"value\":\"\"},\"35b482dd09d535d8e6833d6f24a1f3ac\":{\"date\":1717117581497,\"value\":\"1717117609552IMLGoQqQn8b9ukD8ADM\"}}; lang=zh-cn; aws-waf-token=4f277a12-33c3-47b0-b891-3b1c994598a3:AQoAk90IensBAAAA:zstdi0kpdQTK1eAueTZM0Hh4ZylfGhcOfSkRTZMcriiyQ0d77q8T5XvBzmFHgXU5fPgsb4HPRGqXQwX5c2kkCTPc9g8JmKQ4Yy6WIWLVqzfx4CqXHzl4oshnHIrrIMFIHg6uvmt2UYkguCqdRsg1z5Ga2qhyohgDoal4d/E4X6dfp2k4iLp2JZ9Fl5bH7agDKhY=; BNC_FV_KEY_T=101-in4lG9WWi4xeKzQz%2BLe%2F2XPAqJRI%2BXwxzJehyL8H8pFrd%2FNAvyxdNoKwkCJef%2Fgd56WYX7YT19PKfm%2BAlWQnFg%3D%3D-NgpRY2KdsXgrnjMyYAaFug%3D%3D-e4; BNC_FV_KEY_EXPIRE=1736752649829"}
    # 创建BlockingScheduler对象
    scheduler = BlockingScheduler()
    bs.login()
    bs.logout()
    client = Spot()
    marketDataAPI = MarketData.MarketAPI(flag='0', debug=False)
    publicDataAPI = PublicData.PublicAPI(flag='0', debug=False)
    alert_all = {'BN': {}, 'OKX': {}, 'A': {}}
    main()
