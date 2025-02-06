import time
from datetime import datetime

import akshare as ak
import pandas as pd


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
    return zt_df['代码'].tolist()


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
        hist = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
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
            selected.append(code)
    return selected


# 步骤3：实时监控
def monitor_stocks(selected_stocks):
    alert_set = set()
    while True:
        spot_df = ak.stock_zh_a_spot()
        for code in selected_stocks:
            stock_info = spot_df[spot_df['代码'].str.contains(code)]
            if not stock_info.empty:
                current_pct = stock_info['涨跌幅'].values[0]
                upper_limit = get_upper_limit(code, stock_info)
                prev_close = stock_info['昨收'].values[0]
                half_pct = (upper_limit - prev_close) / prev_close * 100 / 2

                if current_pct >= half_pct and code not in alert_set:
                    alert_set.add(code)
                    print(f"[预警] {code} 涨幅达{current_pct:.2f}%，触发条件（{half_pct:.2f}%）")
        time.sleep(60)


if __name__ == "__main__":
    # 主流程
    zt_stocks = get_yesterday_zt_stocks()
    print(f"昨日涨停股：{zt_stocks}")

    filtered = filter_stocks(zt_stocks)
    print(f"符合量能条件的股票：{filtered}")

    monitor_stocks(filtered)
