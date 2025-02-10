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
from apscheduler.schedulers.background import BackgroundScheduler
from binance.spot import Spot


def bn():
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
                # return {symbol: (kline[-1][4], 0, 100, 3000)}
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
            if kline[index_e][5] < kline[index_e + 1][5] * 2 or kline[-2][
                2] > price_close:  # or price_low < kline[index_e][1] or price_high > price_close or kline[-2][4] >= price_high:
                return
            max_decimal = max(map(get_max_decimal_places, map(str, kline_close)))
            price_vol = kline[-index_d - 1][4]
            zf = round((kline[-2][4] / kline[index_s][1] - 1) * 100, 2)
            zf_m = zf / (len(kline) - 1 - index_s)
            price_zy = round(kline[-2][4] + kline[-2][4] * zf_m / 100, max_decimal)
            expectation = round((price_zy / kline[-2][2] - 1) * 100, 2)
            if expectation < 0:
                price_zy = round(kline[-2][2] + kline[-2][2] * abs(expectation) / 100, max_decimal)
                return
            if price_zy > kline[-1][2]:
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
                    "text": {'content': f'==={market}{len(alert)}做多===\n' + '\n-------\n'.join(alert_final)}
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
            with open('symbol.json', 'w') as f:
                json.dump(alert, f, indent=4, ensure_ascii=False)
            print(datetime.datetime.now(), f'{market}任务结束', alert_final, alert)
            gc.collect()

    def main():
        # symbols_a = [c[0] for c in bs.query_all_stock().data if 'ST' not in c[-1]]
        symbols_bn = []
        symbols_okx = []
        for i in range(10):
            try:
                # 获取所有交易对信息
                exchange_info = client.exchange_info()
                # 提取所有交易对
                symbols_bn = [symbol['symbol'] for symbol in exchange_info['symbols'] if
                              'USDT' in symbol['quoteAsset'] and 'TRADING' in symbol['status']]
                # res = session.get('https://www.binance.com/zh-CN/markets/overview?p=1')
                # data = json.loads(etree.HTML(res.text).xpath('//*[@id="__APP_DATA"]//text()')[0])
                # symbols_bn = [item['symbol'] for item in parse('$..productMap').find(data)[0].value.values() if
                #               item.get('quoteAsset') == 'USDT']
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

    requests.packages.urllib3.disable_warnings()
    session = requests.Session()
    session.verify = False
    session.headers = {'Content-Type': 'application/json',
                       'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
                       'Cookie': "theme=dark; bnc-uuid=864a564f-ccf6-4f85-9d4b-81101eee187b; sajssdk_2015_cross_new_user=1; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22194cc29591f959-089aa74ba4228e-3e3c730c-2359296-194cc295920b51%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk0Y2MyOTU5MWY5NTktMDg5YWE3NGJhNDIyOGUtM2UzYzczMGMtMjM1OTI5Ni0xOTRjYzI5NTkyMGI1MSJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%7D; OptanonAlertBoxClosed=2025-02-03T14:14:13.381Z; BNC_FV_KEY=33d482edf8e0a2b7a317d792ab8a5a79da3b672c; BNC_FV_KEY_T=101-lG%2F8JaMW%2F08tiozMmqbAnQ6H%2Fg7a4nWIUoYF%2BJszn2KMVlOA7Q4hlvgnMYSB7%2FKxKxvsktk%2FpcV0CI%2BxGdr6ag%3D%3D-nOdqJuQ0TfGh96V4oxln%2Bw%3D%3D-f5; BNC_FV_KEY_EXPIRE=1738613653411; _gid=GA1.2.1723640189.1738592055; aws-waf-token=5af9f84f-93be-4e1d-ace7-82b501a292fb:AQoAfLBkBx0NAAAA:Pcju4WtH/yKaqK2hXsRRjKzLSK0ieQoDiZTXc1bZ31t16xqV4vKMWhf3/v6VMwLen/iPAj21QBZ/nMfSytJXbhR2beNiDYv+6tgEawlaidIA3lHn5+cuMl52DBGDc559yARJA/B/hcPUkR9v7LtxEhevaz8rdXJoysOPs2vYtRUTa/4/F1MWy0OhBZHy5/4/YsJhV3VPIafh8TTa5d7pGzaz; OptanonConsent=isGpcEnabled=0&datestamp=Mon+Feb+03+2025+22%3A16%3A28+GMT%2B0800+(%E4%B8%AD%E5%9B%BD%E6%A0%87%E5%87%86%E6%97%B6%E9%97%B4)&version=202411.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=a832b7ee-2adf-4c9f-899d-28d15dbbb663&interactionCount=1&isAnonUser=1&landingPath=NotLandingPage&groups=C0001%3A1%2CC0003%3A1%2CC0004%3A1%2CC0002%3A1&intType=1&geolocation=JP%3B27&AwaitingReconsent=false; _ga_3WP50LGEEC=GS1.1.1738592056.1.1.1738592190.52.0.0; _ga=GA1.1.1073516655.1738592055"
                       }
    # 创建BlockingScheduler对象
    scheduler = BackgroundScheduler()
    bs.login()
    bs.logout()
    client = Spot()
    marketDataAPI = MarketData.MarketAPI(flag='0', debug=False)
    publicDataAPI = PublicData.PublicAPI(flag='0', debug=False)
    alert_all = {'BN': {}, 'OKX': {}, 'A': {}}
    main()
