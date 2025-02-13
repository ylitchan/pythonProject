from datetime import datetime

import akshare as ak
import pandas as pd
import requests
from apscheduler.schedulers.blocking import BlockingScheduler


def a():
    # 辅助函数：获取股票涨停价
    def get_upper_limit(code, stock_info):
        name = stock_info['名称'].values[0]
        prev_close = stock_info['昨收'].values[0]
        if 'ST' in name or '*ST' in name:
            return round(prev_close * 1.05, 2)  # ST股涨停5%
        elif code.startswith(('300', '688')):  # 创业板和科创板涨停20%
            return round(prev_close * 1.2, 2)
        else:  # 其他股票涨停10%
            return round(prev_close * 1.1, 2)

    def get_last_three_trading_days(days=3):
        # 获取最近的交易日列表
        trade_dates = ak.tool_trade_date_hist_sina()
        trade_dates = pd.to_datetime(trade_dates["trade_date"])  # 转换为 datetime

        # 找到最近的三个交易日
        today = datetime.today()
        recent_trading_days = trade_dates[trade_dates <= today].sort_values(ascending=False).iloc[:days]
        start_date = recent_trading_days.min().strftime("%Y%m%d")
        end_date = recent_trading_days.max().strftime("%Y%m%d")
        return start_date, end_date

    # 步骤1：获取昨日涨停股票列表
    def get_yesterday_zt_stocks():
        # 获取最近交易日（这里假设昨日是20231009，实际应自动获取）
        start_date, end_date = get_last_three_trading_days()
        zt_df = ak.stock_zt_pool_em(date=start_date)
        if zt_df.empty:
            print(f"没有在 {start_date} 找到涨停股票。")
            return []
        return zt_df[['代码', '名称']].values.tolist()

    # 步骤2：筛选符合条件的股票
    def filter_stocks(stock_codes):
        # 获取最近的交易日列表
        trade_dates = ak.tool_trade_date_hist_sina()
        trade_dates = pd.to_datetime(trade_dates["trade_date"])  # 转换为 datetime

        # 找到最近的三个交易日
        today = datetime.today()
        recent_trading_days = trade_dates[trade_dates <= today].sort_values(ascending=False).iloc[:3]
        start_date = recent_trading_days.min().strftime("%Y%m%d")
        end_date = recent_trading_days.max().strftime("%Y%m%d")
        selected = []
        # spot_df = ak.stock_zh_a_spot()
        for code in stock_codes:
            # 获取历史数据（昨日量能）
            hist = ak.stock_zh_a_hist(symbol=code[0], period="daily", start_date=start_date, end_date=end_date,
                                      adjust="qfq")
            if len(hist) < 3: continue
            yesterday_vol = hist.iloc[-2]['成交量']
            yesterday_yesterday_vol = hist.iloc[-3]['成交量']
            yesterday_pct = hist.iloc[-2]['涨跌幅']
            # 获取今日实时数据
            # spot_data = spot_df[spot_df['代码'].str.contains(code)]
            # if spot_data.empty: continue

            # today_vol = spot_data['成交量'].values[0]
            # today_pct = spot_data['涨跌幅'].values[0]

            if yesterday_vol <= yesterday_yesterday_vol and yesterday_pct <= 0:
                selected.append(''.join(code))
        return selected

    # 步骤3：实时监控
    def monitor_stocks():
        zt_stocks = get_yesterday_zt_stocks()
        print(f"昨日涨停股：{zt_stocks}")
        filtered = filter_stocks(zt_stocks)
        print(f"符合量能条件的股票：{filtered}")
        json_msg = {
            "msgtype": "text",
            "text": {'content': f'===A{len(filtered)}打板===\n' + '\n-------\n'.join(filtered)}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
            json=json_msg)
        # alert_set = set()
        # while True:
        #     spot_df = ak.stock_zh_a_spot()
        #     for code in selected_stocks:
        #         stock_info = spot_df[spot_df['代码'].str.contains(code)]
        #         if not stock_info.empty:
        #             current_pct = stock_info['涨跌幅'].values[0]
        #             upper_limit = get_upper_limit(code, stock_info)
        #             prev_close = stock_info['昨收'].values[0]
        #             half_pct = (upper_limit - prev_close) / prev_close * 100 / 2
        #
        #             if current_pct >= half_pct and code not in alert_set:
        #                 alert_set.add(code)
        #                 print(f"[预警] {code} 涨幅达{current_pct:.2f}%，触发条件（{half_pct:.2f}%）")
        #     time.sleep(60)

    if __name__ == "__main__":
        requests.packages.urllib3.disable_warnings()
        session = requests.Session()
        session.verify = False
        session.headers = {'Content-Type': 'application/json',
                           'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
                           'Cookie': "theme=dark; bnc-uuid=864a564f-ccf6-4f85-9d4b-81101eee187b; sajssdk_2015_cross_new_user=1; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22194cc29591f959-089aa74ba4228e-3e3c730c-2359296-194cc295920b51%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk0Y2MyOTU5MWY5NTktMDg5YWE3NGJhNDIyOGUtM2UzYzczMGMtMjM1OTI5Ni0xOTRjYzI5NTkyMGI1MSJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%7D; OptanonAlertBoxClosed=2025-02-03T14:14:13.381Z; BNC_FV_KEY=33d482edf8e0a2b7a317d792ab8a5a79da3b672c; BNC_FV_KEY_T=101-lG%2F8JaMW%2F08tiozMmqbAnQ6H%2Fg7a4nWIUoYF%2BJszn2KMVlOA7Q4hlvgnMYSB7%2FKxKxvsktk%2FpcV0CI%2BxGdr6ag%3D%3D-nOdqJuQ0TfGh96V4oxln%2Bw%3D%3D-f5; BNC_FV_KEY_EXPIRE=1738613653411; _gid=GA1.2.1723640189.1738592055; aws-waf-token=5af9f84f-93be-4e1d-ace7-82b501a292fb:AQoAfLBkBx0NAAAA:Pcju4WtH/yKaqK2hXsRRjKzLSK0ieQoDiZTXc1bZ31t16xqV4vKMWhf3/v6VMwLen/iPAj21QBZ/nMfSytJXbhR2beNiDYv+6tgEawlaidIA3lHn5+cuMl52DBGDc559yARJA/B/hcPUkR9v7LtxEhevaz8rdXJoysOPs2vYtRUTa/4/F1MWy0OhBZHy5/4/YsJhV3VPIafh8TTa5d7pGzaz; OptanonConsent=isGpcEnabled=0&datestamp=Mon+Feb+03+2025+22%3A16%3A28+GMT%2B0800+(%E4%B8%AD%E5%9B%BD%E6%A0%87%E5%87%86%E6%97%B6%E9%97%B4)&version=202411.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=a832b7ee-2adf-4c9f-899d-28d15dbbb663&interactionCount=1&isAnonUser=1&landingPath=NotLandingPage&groups=C0001%3A1%2CC0003%3A1%2CC0004%3A1%2CC0002%3A1&intType=1&geolocation=JP%3B27&AwaitingReconsent=false; _ga_3WP50LGEEC=GS1.1.1738592056.1.1.1738592190.52.0.0; _ga=GA1.1.1073516655.1738592055"}
        monitor_stocks()
        # 主流程
        # zt_stocks = get_yesterday_zt_stocks()
        # print(f"昨日涨停股：{zt_stocks}")
        #
        # filtered = filter_stocks(zt_stocks)
        # print(f"符合量能条件的股票：{filtered}")
        scheduler = BlockingScheduler()
        scheduler.add_job(monitor_stocks, 'cron', hour='9', minute='30', second='00', timezone='Asia/Shanghai')
        # 启动调度器
        scheduler.start()
        # monitor_stocks(filtered)
