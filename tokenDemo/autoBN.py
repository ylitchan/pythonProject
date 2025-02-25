import asyncio
import datetime
import gc
import json
import re
import traceback

import akshare as ak
import pandas as pd
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from binance.spot import Spot
from jsonpath_ng import parse


def trade(symbol, price, stopPrice, symbols_info):
    try:
        if (usdt_free := float(spotBN.user_asset(asset='USDT')[0]['free'])) / 2 < 6:
            return
        minQty = symbols_info.get(symbol).get('minQty')
        quotePrecision = symbols_info.get(symbol).get('quotePrecision')
        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quoteOrderQty": round(usdt_free, quotePrecision)
        }
        spotBN.new_order(**params)
        symbol_free = float(spotBN.user_asset(asset=symbol[:-4])[0]['free'])
        symbol_free_round = round(symbol_free, minQty)
        if symbol_free_round > symbol_free:
            symbol_free_round = symbol_free_round - 10 ** -minQty
        params = {
            "symbol": symbol,
            "side": "SELL",
            "quantity": symbol_free_round,
            "price": price,
            "stopPrice": stopPrice
        }
        spotBN.new_oco_order(**params)
        return symbol
    except:
        traceback.print_exc()
        return


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


async def get_kline(semaphore, symbol, t: str):
    async with semaphore:
        kline = await asyncio.to_thread(spotBN.klines, symbol=symbol, interval=t[:2].lower(), limit=20)
        kline = [list(map(float, sublist)) for sublist in kline]
        return kline


def get_max_decimal_places(price_s):
    if p := re.search('\.\d+', price_s):
        return len(p.group()) - 1
    return 0


async def rzq_token(semaphore, symbol, alert, success, alert_m):
    try:
        kline = await get_kline(semaphore, symbol, "1Dutc")
        success.add(symbol)
        # if symbol == 'ETHUSDT' and kline[-1][4] <= 3000:
        #     data = {symbol: (kline[-1][4], 0, 100, 3000, 3000)}
        #     alert.update(data)
        #     return data
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
        price_close = kline[-1][4]
        if kline[index_e][5] < max([k[5] for k in kline[:index_e]]) * 2 or kline[-2][
            2] > price_close:
            return
        max_decimal = max(map(get_max_decimal_places, map(str, kline_close)))
        zf = round(sum(map(lambda k: k[4] / k[1] - 1, kline)) * 100, 2)
        zf_m = zf / (len(kline) - 1 - index_s)
        price_zy = round(kline[-2][4] + kline[-2][4] * zf_m / 100, max_decimal)
        expectation = round((price_zy / kline[-2][2] - 1) * 100, 2)
        if expectation < 0:
            return
        if price_zy > kline[-1][2]:
            price_zs = kline[index_e][3]
            data = {symbol: (price_close, zf, expectation, price_zy, price_zs)}
            alert.update(data)
            alert_m.update(data)
            return data
    except:
        traceback.print_exc()
        return


async def rzq_market(market):
    now = datetime.datetime.now()
    symbols = []
    alert = alert_all.get(market, {})
    for i in range(10):
        try:
            # 获取所有交易对信息
            exchange_info = await asyncio.to_thread(spotBN.exchange_info)
            # 提取所有交易对
            symbols_info = {symbol['symbol']: {'quotePrecision': symbol['quotePrecision'], 'minQty': len(str(max(
                map(lambda x: float(x), [y.value for y in parse('$..minQty').find(symbol)]))))} for symbol in
                            exchange_info['symbols'] if
                            symbol['symbol'] not in alert and 'USDT' in symbol['quoteAsset'] and 'TRADING' in symbol[
                                'status']}
            symbols = list(symbols_info.keys())
            break
        except:
            traceback.print_exc()
            await asyncio.sleep(2)
    semaphore = asyncio.Semaphore(10)  # 限制 2 个并发
    print(now, f'{market}任务开始', len(symbols))
    POSITIONS = alert_all.get("POSITIONS", {})
    if now.hour == 8 and now.minute < 2:
        alert.clear()
        POSITIONS.clear()
    success = set()
    alert_m = {}
    alert_final = []
    tasks = [rzq_token(semaphore, symbol, alert, success, alert_m) for symbol in symbols]
    await asyncio.gather(*tasks)
    try:
        print(market, f"""{len(success)}/{len(symbols)}""")
        if alert_m:
            alert_sort = enumerate(sorted(alert, key=lambda x: alert[x][2], reverse=True))
            for i, j in alert_sort:
                if j not in alert_m:
                    continue
                if j not in POSITIONS:
                    if trade(symbol=j, price=alert_m[j][3], stopPrice=alert_m[j][4], symbols_info=symbols_info):
                        POSITIONS.update({j: alert_m[j]})
                if j in POSITIONS:
                    alert_final.append(
                        f'开仓{i + 1}.{j.replace("-USDT", "USDT")[:-4]}\n'
                        f'现价:{alert_m[j][0]}\n涨幅:{alert_m[j][1]}\n预期:{alert_m[j][2]}\n止盈:{alert_m[j][3]}\n止损:{alert_m[j][4]}')
                else:
                    alert_final.append(
                        f'{i + 1}.{j.replace("-USDT", "USDT")[:-4]}\n'
                        f'现价:{alert_m[j][0]}\n涨幅:{alert_m[j][1]}\n预期:{alert_m[j][2]}\n止盈:{alert_m[j][3]}\n止损:{alert_m[j][4]}')
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
    today = datetime.datetime.today()
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
    today = datetime.datetime.today()
    recent_trading_days = trade_dates[trade_dates <= today].sort_values(ascending=False).iloc[:3]
    start_date = recent_trading_days.min().strftime("%Y%m%d")
    end_date = recent_trading_days.max().strftime("%Y%m%d")
    selected = []
    # spot_df = ak.stock_zh_a_spot()
    for code in stock_codes:
        try:
            # 获取历史数据（昨日量能）
            hist = ak.stock_zh_a_hist(symbol=code[0], period="daily", start_date=start_date, end_date=end_date,
                                      adjust="qfq")
        except:
            traceback.print_exc()
            continue
        if len(hist) < 3: continue
        yesterday_yesterday_pct = hist.iloc[-3]['涨跌幅']
        yesterday_pct = hist.iloc[-2]['涨跌幅']
        # 获取今日实时数据
        # spot_data = spot_df[spot_df['代码'].str.contains(code)]
        # if spot_data.empty: continue

        # today_vol = spot_data['成交量'].values[0]
        # today_pct = spot_data['涨跌幅'].values[0]

        if yesterday_pct <= -yesterday_yesterday_pct / 2:
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


async def main():
    await rzq_market('BN')
    # 设置任务调度
    scheduler.add_job(monitor_stocks, 'cron', hour='9', minute='30', second='00', day_of_week='mon-fri',
                      timezone='Asia/Shanghai')
    scheduler.add_job(rzq_market, 'cron', hour='*', minute='*/1', second='00', timezone='Asia/Shanghai',
                      args=('BN',))
    # 启动调度器
    scheduler.start()
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发


if __name__ == "__main__":
    session = requests.Session()
    session.verify = False
    session.headers = {'Content-Type': 'application/json'}
    # 创建BlockingScheduler对象
    scheduler = AsyncIOScheduler()
    with open('bn.json', 'r') as f:
        bn_api = json.load(f)
    spotBN = Spot(api_key=bn_api.get('api_key'), api_secret=bn_api.get('api_secret'))
    alert_all = {'BN': {}, 'POSITIONS': {}}
    asyncio.run(main())
