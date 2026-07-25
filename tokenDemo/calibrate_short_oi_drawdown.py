"""BD空头OI回撤阈值校准.

拉取全部USDT永续近30天的1d OI与日K, 统计:
1) 日度OI噪声与距30日峰值回撤的无条件分布(基准率)
2) BD型信号(价量创30日新高)后的OI回撤分布与前瞻收益 -> 校准阈值X
3) 回撤X / 切比雪夫<5% / 低于基线均值 三条件的重叠度与各自边际价值

注: Binance openInterestHist 仅保留最近30天, 属单月横截面样本.
用法: PYTHONIOENCODING=utf-8 uv run python tokenDemo/calibrate_short_oi_drawdown.py
"""

import asyncio
import statistics

import aiohttp

BASE_URL = "https://fapi.binance.com"
CONCURRENCY = 8
OI_LIMIT = 30
KLINE_FETCH_LIMIT = 70  # 需覆盖OI窗口前29天的价量新高回看
SIGNAL_WINDOW = 30  # 价量新高回看窗口, 与 AUTOBN.KLINE_LIMIT=30 对齐
BASELINE_LEN = 20  # 切比雪夫基线取最近20根, 与策略 [-20:] 一致
MIN_TRAILING_OI = 15  # 计算回撤/基线所需最少trailing天数
CHEB_THRESHOLD = 0.05  # 与 SHORT_OI_CHEB_THRESHOLD 一致
RALLY_LOOKBACK = 5  # 冲顶段OI变化的回看天数(信号日 vs 前5日), 检验空头燃尽理念
BZ_OI_DAY_SURGE = 0.05  # BZ型日的OI日增代理阈值(实盘BZ用5m/1h粒度+切比雪夫, 日线只能近似)
BZ_RECENT_DAYS = 5  # 入池检查"近N日内出过BZ型日"
VOLUME_LOOKBACK = 10  # BZ量条件回看天数, 与策略 VOLUME_LOOKBACK_PERIOD 一致
TRIGGER_LAGS = (3, 4, 5)  # 扣扳机窗口: 顶后第3-5天
DD_SWEEP = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
DAY_MS = 86_400_000


async def fetch_json(session, sem, path, params=None):
    async with sem:
        for _ in range(3):
            try:
                async with session.get(
                    f"{BASE_URL}{path}",
                    params=params or {},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status in (418, 429):
                        await asyncio.sleep(10)
                        continue
                    if resp.status != 200:
                        return None
                    return await resp.json()
            except Exception:
                await asyncio.sleep(2)
        return None


def cheb_stats(baseline, value):
    """返回 (切比雪夫上界, 基线均值), 算法与 AUTOBN.calculate_chebyshev_probability 一致."""
    mean = sum(baseline) / len(baseline)
    var = sum((x - mean) ** 2 for x in baseline) / (len(baseline) - 1)
    std = var**0.5
    if std == 0:
        return 0.0, mean
    k = abs(value - mean) / std
    ub = 1.0 if k <= 1 else 1 / (k * k)
    return ub, mean


def quantile(vals, q):
    s = sorted(vals)
    if not s:
        return float("nan")
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def process_symbol(oi_raw, klines):
    kl = {int(k[0]) // DAY_MS: (float(k[4]), float(k[5])) for k in klines}
    oi_days = sorted(
        (int(x["timestamp"]) // DAY_MS, float(x["sumOpenInterest"])) for x in oi_raw
    )
    days = [d for d, _ in oi_days]
    vals = [v for _, v in oi_days]
    n = len(vals)
    day_index = {d: i for i, d in enumerate(days)}

    kdays = sorted(kl)
    kidx = {d: i for i, d in enumerate(kdays)}
    closes_arr = [kl[d][0] for d in kdays]

    def price_high_info(d):
        """返回 (收盘距30日收盘高点的距离, 距高点天数); 覆盖不足15根时返回(None, None)."""
        if d not in kidx:
            return None, None
        i = kidx[d]
        lo = max(0, i - SIGNAL_WINDOW + 1)
        win = closes_arr[lo : i + 1]
        if len(win) < 15:
            return None, None
        arg = max(range(len(win)), key=win.__getitem__)
        return win[-1] / max(win) - 1, len(win) - 1 - arg

    def dd_at(i):
        peak = max(vals[: i + 1])
        return 1 - vals[i] / peak if peak > 0 else 0.0

    def snapshot(i):
        value = vals[i]
        baseline = vals[max(0, i - BASELINE_LEN + 1) : i + 1]
        ub, mean = cheb_stats(baseline, value)
        return {
            "dd": dd_at(i),
            "cheb": ub < CHEB_THRESHOLD,
            "below": value < mean,
            "old": value <= min(vals[: i + 1]),
        }

    day_records = []
    for i in range(MIN_TRAILING_OI - 1, n):
        rec = snapshot(i)
        d = days[i]
        rec["chg"] = (
            abs(vals[i] / vals[i - 1] - 1) if i > 0 and vals[i - 1] > 0 else None
        )
        rec["oi_chg"] = vals[i] / vals[i - 1] - 1 if i > 0 and vals[i - 1] > 0 else None
        rec["p_chg"] = (
            kl[d][0] / kl[d - 1][0] - 1 if d in kl and (d - 1) in kl else None
        )
        rec["off_high"], rec["days_since_high"] = price_high_info(d)
        rec["oi_chg3"] = (
            vals[i] / vals[i - 3] - 1 if i >= 3 and vals[i - 3] > 0 else None
        )
        for h in (1, 3, 5):
            rec[f"fwd{h}"] = (
                kl[d + h][0] / kl[d][0] - 1 if d in kl and (d + h) in kl else None
            )
        day_records.append(rec)

    # BD型信号日: 收盘价为30日窗口最大(需完整30根日K); 价量双高为现行BD口径
    sig_days_p = []  # 仅价格创30日新高
    sig_days = []  # 价量双高(现行BD)
    for d in days:
        window = [kl.get(d - off) for off in range(SIGNAL_WINDOW)]
        if any(w is None for w in window):
            continue
        closes = [w[0] for w in window]
        volumes = [w[1] for w in window]
        if closes[0] >= max(closes):
            sig_days_p.append(d)
            if volumes[0] >= max(volumes):
                sig_days.append(d)

    # BZ型日(日线代理): 当日价涨 + 量>=近10日最大 + OI日增>=阈值
    # 实盘BZ用5m/1h粒度+切比雪夫<1%, 日线只能近似其"价拉+放量+OI剧增"三要素
    bz_days = []
    for d in days:
        i = day_index[d]
        if i < 1 or vals[i - 1] <= 0:
            continue
        vol_win = [kl.get(d - off) for off in range(VOLUME_LOOKBACK + 1)]
        if any(w is None for w in vol_win):
            continue
        if (
            kl[d][0] > kl[d - 1][0]
            and kl[d][1] >= max(w[1] for w in vol_win)
            and vals[i] / vals[i - 1] - 1 >= BZ_OI_DAY_SURGE
        ):
            bz_days.append(d)

    sig_p_set = set(sig_days_p)
    sig_pv_set = set(sig_days)
    # 链条验证: BZ型日后0-3天内是否出现30日价格新高
    chain_total = len(bz_days)
    chain_hits = sum(
        1 for b in bz_days if any((b + k) in sig_p_set for k in range(0, 4))
    )

    def dedupe(sig):
        out = []
        for idx, d in enumerate(sig):
            if idx + 1 < len(sig) and sig[idx + 1] == d + 1:
                continue
            out.append(d)
        return out

    def near_bz(d):
        return any(0 <= d - b <= BZ_RECENT_DAYS for b in bz_days)

    def oi_pool_cheb(d):
        """入池OI切比雪夫(用户提案): 锚日近10日OI最大值 vs 之前基线(最多20日)的上界."""
        i = day_index.get(d)
        if i is None:
            return None
        hist = vals[max(0, i - 29) : i + 1]
        if len(hist) < 20:
            return None
        ub, _ = cheb_stats(hist[:-10], max(hist[-10:]))
        return ub

    def cheb_pool(anchors, thr):
        out = []
        for d in anchors:
            ub = oi_pool_cheb(d)
            if ub is not None and ub < thr:
                out.append(d)
        return out

    def days_since_vol_peak(d):
        """锚日回看30日窗口内, 成交量峰值距今天数(0=当日即量峰); 窗口不足返回None."""
        i = kidx.get(d)
        if i is None:
            return None
        lo = max(0, i - SIGNAL_WINDOW + 1)
        win = [kl[kdays[j]][1] for j in range(lo, i + 1)]
        if len(win) < 15:
            return None
        arg = max(range(len(win)), key=win.__getitem__)
        return len(win) - 1 - arg

    def trigger_events(anchors, lags=TRIGGER_LAGS):
        """扣扳机: 顶后指定天数窗口内首个 OI dd>=10% 的日子入场."""
        evs = []
        for d in anchors:
            for lag in lags:
                e = d + lag
                if e not in day_index or e not in kl:
                    continue
                i = day_index[e]
                if i < MIN_TRAILING_OI - 1:
                    continue
                if dd_at(i) >= 0.10:
                    rec = {"lag": lag, "vpk": days_since_vol_peak(d)}
                    for h in (1, 3, 5):
                        rec[f"fwd{h}"] = (
                            kl[e + h][0] / kl[e][0] - 1 if (e + h) in kl else None
                        )
                    evs.append(rec)
                    break
        return evs

    anchors_pv = dedupe(sig_days)
    anchors_p = dedupe(sig_days_p)
    # H池锚: OI切比堆积(<5%)且顶日非同日天量(反BZ排除)
    h_anchors = [d for d in cheb_pool(anchors_p, 0.05) if d not in sig_pv_set]
    pools = {
        "A 现行BD(价量双高30日)": trigger_events(anchors_pv),
        "B 仅价创30日高(去天量)": trigger_events(anchors_p),
        "C 价高30日+近5日BZ型日": trigger_events([d for d in anchors_p if near_bz(d)]),
        "D 价量双高+近5日BZ型日": trigger_events([d for d in anchors_pv if near_bz(d)]),
        "E 价高+OI10日max切比<1%": trigger_events(cheb_pool(anchors_p, 0.01)),
        "F 价高+OI10日max切比<5%": trigger_events(cheb_pool(anchors_p, 0.05)),
        "G 价量双高+OI10日max切比<5%": trigger_events(cheb_pool(anchors_pv, 0.05)),
        "H F剔除G(切比堆积但非天量,反BZ排除)": trigger_events(h_anchors),
        "H2 H池+顶后1-5天全窗扣扳机": trigger_events(h_anchors, (1, 2, 3, 4, 5)),
        "I 价高+切比<5%+量峰不在近3天(全窗)": trigger_events(
            [
                d
                for d in cheb_pool(anchors_p, 0.05)
                if (days_since_vol_peak(d) or 0) >= 3
            ],
            (1, 2, 3, 4, 5),
        ),
        "J 价高+切比<5%(不排量,全窗)": trigger_events(
            cheb_pool(anchors_p, 0.05), (1, 2, 3, 4, 5)
        ),
    }
    pool_anchor_counts = {
        "A 现行BD(价量双高30日)": len(anchors_pv),
        "B 仅价创30日高(去天量)": len(anchors_p),
        "C 价高30日+近5日BZ型日": len([d for d in anchors_p if near_bz(d)]),
        "D 价量双高+近5日BZ型日": len([d for d in anchors_pv if near_bz(d)]),
        "E 价高+OI10日max切比<1%": len(cheb_pool(anchors_p, 0.01)),
        "F 价高+OI10日max切比<5%": len(cheb_pool(anchors_p, 0.05)),
        "G 价量双高+OI10日max切比<5%": len(cheb_pool(anchors_pv, 0.05)),
        "H F剔除G(切比堆积但非天量,反BZ排除)": len(h_anchors),
        "H2 H池+顶后1-5天全窗扣扳机": len(h_anchors),
        "I 价高+切比<5%+量峰不在近3天(全窗)": len(
            [
                d
                for d in cheb_pool(anchors_p, 0.05)
                if (days_since_vol_peak(d) or 0) >= 3
            ]
        ),
        "J 价高+切比<5%(不排量,全窗)": len(cheb_pool(anchors_p, 0.05)),
    }

    events = []
    for idx, d in enumerate(sig_days):
        if idx + 1 < len(sig_days) and sig_days[idx + 1] == d + 1:
            continue  # 连续新高只保留最后一天作为峰值日
        e = d + 1  # 入场评估日(观察写入后24h窗口)
        if e not in day_index:
            continue
        i = day_index[e]
        if i < MIN_TRAILING_OI - 1:
            continue
        rec = snapshot(i)
        # 入场窗口内(入场日与次日快照)可达到的最大回撤, 近似24h内逐分钟检查
        rec["dd_window"] = max(dd_at(j) for j in range(i, min(i + 2, n)))
        # 用户组合理念: OI的trailing峰值是否落在最近3天(含入场日) —— 顶部杠杆是新鲜堆积的
        trailing = vals[: i + 1]
        p_idx = max(range(len(trailing)), key=trailing.__getitem__)
        rec["oi_peak_recent"] = p_idx >= len(trailing) - 3
        # 冲顶段OI变化: 信号日(峰值日)OI vs 其前RALLY_LOOKBACK日 —— 缩=空头燃尽/多头谨慎, 增=杠杆堆积
        j = i - 1  # 信号日在OI序列中的下标(入场日=信号日次日)
        rec["rally_oi"] = (
            vals[j] / vals[j - RALLY_LOOKBACK] - 1
            if j - RALLY_LOOKBACK >= 0 and vals[j - RALLY_LOOKBACK] > 0
            else None
        )
        rec["oi_chg"] = vals[i] / vals[i - 1] - 1 if i > 0 and vals[i - 1] > 0 else None
        rec["p_chg"] = (
            kl[e][0] / kl[e - 1][0] - 1 if e in kl and (e - 1) in kl else None
        )
        for h in (1, 3, 5):
            rec[f"fwd{h}"] = (
                kl[e + h][0] / kl[e][0] - 1 if e in kl and (e + h) in kl else None
            )
        events.append(rec)

    # BD顶后第N天入场的对照: 顶后1-5天每天记录 (当日dd, 前瞻收益)
    # A池(现行价量双高)与H池(切比堆积非天量)各记一条, 用pool字段区分
    lag_records = []
    for pool_tag, anchor_list in (("A", dedupe(sig_days)), ("H", h_anchors)):
        for d in anchor_list:
            for lag in range(1, 6):
                e = d + lag
                if e not in day_index or e not in kl:
                    continue
                i = day_index[e]
                if i < MIN_TRAILING_OI - 1:
                    continue
                lag_records.append(
                    {
                        "pool": pool_tag,
                        "lag": lag,
                        "dd": dd_at(i),
                        "fwd3": (
                            kl[e + 3][0] / kl[e][0] - 1 if (e + 3) in kl else None
                        ),
                    }
                )
    return day_records, events, lag_records, pools, pool_anchor_counts, (
        chain_total,
        chain_hits,
    )


def fw(records, key="fwd3"):
    v = [r[key] for r in records if r.get(key) is not None]
    if not v:
        return "n=0"
    neg = sum(1 for x in v if x < 0) / len(v)
    label = key.replace("fwd", "") + "日"
    return (
        f"n={len(v)} 平均{label}收益={statistics.mean(v):+.2%} "
        f"中位={quantile(v, 0.5):+.2%} 下跌占比={neg:.0%}"
    )


async def main():
    sem = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        info = await fetch_json(session, sem, "/fapi/v1/exchangeInfo")
        if not info:
            print("exchangeInfo 获取失败")
            return
        symbols = [
            s["symbol"]
            for s in info["symbols"]
            if s.get("contractType") == "PERPETUAL"
            and s.get("status") == "TRADING"
            and s.get("quoteAsset") == "USDT"
        ]
        print(f"USDT永续标的: {len(symbols)}")

        async def load(sym):
            oi, kl = await asyncio.gather(
                fetch_json(
                    session,
                    sem,
                    "/futures/data/openInterestHist",
                    {"symbol": sym, "period": "1d", "limit": OI_LIMIT},
                ),
                fetch_json(
                    session,
                    sem,
                    "/fapi/v1/klines",
                    {"symbol": sym, "interval": "1d", "limit": KLINE_FETCH_LIMIT},
                ),
            )
            if not oi or not kl or len(oi) < MIN_TRAILING_OI:
                return None
            return process_symbol(oi, kl)

        results = await asyncio.gather(*(load(s) for s in symbols))

    all_days, all_events, all_lags = [], [], []
    all_pools, all_pool_anchors = {}, {}
    chain_total = chain_hits = 0
    ok = 0
    for r in results:
        if r is None:
            continue
        ok += 1
        all_days.extend(r[0])
        all_events.extend(r[1])
        all_lags.extend(r[2])
        for k, v in r[3].items():
            all_pools.setdefault(k, []).extend(v)
        for k, v in r[4].items():
            all_pool_anchors[k] = all_pool_anchors.get(k, 0) + v
        chain_total += r[5][0]
        chain_hits += r[5][1]
    print(f"有效标的: {ok}  样本日: {len(all_days)}  BD型信号事件: {len(all_events)}")

    chgs = [r["chg"] for r in all_days if r["chg"] is not None]
    dds = [r["dd"] for r in all_days]
    print("\n=== 无条件基准(全币种 x 全样本日) ===")
    print(
        f"日度|ΔOI|: p50={quantile(chgs, 0.5):.1%} "
        f"p75={quantile(chgs, 0.75):.1%} p90={quantile(chgs, 0.9):.1%}"
    )
    print(
        f"距30日OI峰值回撤: p50={quantile(dds, 0.5):.1%} "
        f"p75={quantile(dds, 0.75):.1%} p90={quantile(dds, 0.9):.1%}"
    )
    for x in DD_SWEEP:
        share = sum(1 for v in dds if v >= x) / len(dds)
        print(f"  任意日 dd>={x:.0%} 基准率: {share:.1%}")
    old_share = sum(1 for r in all_days if r["old"]) / len(all_days)
    cb_share = sum(1 for r in all_days if r["cheb"] and r["below"]) / len(all_days)
    print(f"  旧条件(<=trailing min) 基准率: {old_share:.1%}")
    print(f"  cheb<5% 且 低于基线均值 基准率: {cb_share:.1%}")

    d10 = [r for r in all_days if r["dd"] >= 0.10]
    print(f"\n=== 条件重叠(全样本日, dd>=10% 子集 n={len(d10)}) ===")
    if d10:
        cheb_in = sum(r["cheb"] for r in d10) / len(d10)
        below_in = sum(r["below"] for r in d10) / len(d10)
        both_in = sum(r["cheb"] and r["below"] for r in d10) / len(d10)
        print(
            f"dd>=10% 中: cheb通过 {cheb_in:.0%} | 低于均值 {below_in:.0%} | 两者同时 {both_in:.0%}"
        )
        cb = [r for r in all_days if r["cheb"] and r["below"]]
        if cb:
            dd_in_cb = sum(r["dd"] >= 0.10 for r in cb) / len(cb)
            print(f"cheb&方向通过 中: dd>=10% 占 {dd_in_cb:.0%} (n={len(cb)})")
        print(f"  dd>=10% & cheb通过:   {fw([r for r in d10 if r['cheb']])}")
        print(f"  dd>=10% & cheb不过:   {fw([r for r in d10 if not r['cheb']])}")
        print(f"  dd>=10% & 高于均值:   {fw([r for r in d10 if not r['below']])}")

    print("\n=== BD型信号事件(价量创30日新高, 入场日=峰值次日) ===")
    if all_events:
        de = [e["dd"] for e in all_events]
        dw = [e["dd_window"] for e in all_events]
        print(
            f"入场日dd: p25={quantile(de, 0.25):.1%} p50={quantile(de, 0.5):.1%} "
            f"p75={quantile(de, 0.75):.1%} p90={quantile(de, 0.9):.1%}"
        )
        print(
            f"入场窗口max dd: p50={quantile(dw, 0.5):.1%} "
            f"p75={quantile(dw, 0.75):.1%} p90={quantile(dw, 0.9):.1%}"
        )
        n_old = sum(e["old"] for e in all_events)
        n_cb = sum(e["cheb"] and e["below"] for e in all_events)
        print(f"旧条件(<=min)通过: {n_old}/{len(all_events)} | cheb&方向通过: {n_cb}")
        evf = [e for e in all_events if e["fwd3"] is not None]
        print(f"全事件基准: {fw(evf)}")
        for x in DD_SWEEP:
            hit = [e for e in evf if e["dd_window"] >= x]
            miss = [e for e in evf if e["dd_window"] < x]
            print(f"X={x:.0%}: 通过 {fw(hit)} || 未通过 {fw(miss)}")

        print(
            f"\n--- 天价天量理念检验: 冲顶段(信号日vs前{RALLY_LOOKBACK}日)OI变化 ---"
        )
        evr = [e for e in evf if e["rally_oi"] is not None]
        ro = [e["rally_oi"] for e in evr]
        if ro:
            print(
                f"冲顶段OI变化分布: p25={quantile(ro, 0.25):+.1%} "
                f"p50={quantile(ro, 0.5):+.1%} p75={quantile(ro, 0.75):+.1%}"
            )
            shrink = [e for e in evr if e["rally_oi"] < 0]
            grow = [e for e in evr if e["rally_oi"] >= 0]
            for label, subset in (
                ("  冲顶OI缩(空头燃尽型)", shrink),
                ("  冲顶OI增(杠杆堆积型)", grow),
            ):
                for h in (1, 3, 5):
                    print(f"{label} {fw(subset, f'fwd{h}')}")
            for label, subset in (
                ("  燃尽型 & 24h内dd>=10%", [e for e in shrink if e["dd_window"] >= 0.10]),
                ("  燃尽型 & 24h内dd<10% ", [e for e in shrink if e["dd_window"] < 0.10]),
                ("  堆积型 & 24h内dd>=10%", [e for e in grow if e["dd_window"] >= 0.10]),
                ("  堆积型 & 24h内dd<10% ", [e for e in grow if e["dd_window"] < 0.10]),
            ):
                print(f"{label} {fw(subset, 'fwd3')}")

        print("\n--- 用户组合理念: 价/量/OI三高齐聚最近3天 + 24h内OI回撤>=10% ---")
        fresh = [e for e in evf if e["oi_peak_recent"]]
        stale = [e for e in evf if not e["oi_peak_recent"]]
        print(f"OI峰值在最近3天(三高齐聚): {len(fresh)}/{len(evf)}")
        for label, subset in (
            ("  三高齐聚 & dd>=10% [完整组合]", [e for e in fresh if e["dd_window"] >= 0.10]),
            ("  三高齐聚 & dd<10%  [引信未点]", [e for e in fresh if e["dd_window"] < 0.10]),
            ("  OI峰值是旧的(>3天前)         ", stale),
        ):
            for h in (1, 3, 5):
                print(f"{label} {fw(subset, f'fwd{h}')}")

    print("\n=== OI下降的两种成因: 价跌(多头认输/撤风险) vs 价涨(空头回补/挤空) ===")
    print(f"  无条件基线(全样本日) {fw(all_days, 'fwd3')}")
    dn = [
        r
        for r in all_days
        if r["oi_chg"] is not None and r["p_chg"] is not None and r["oi_chg"] < -0.02
    ]
    print(f"OI单日跌>2% 样本 n={len(dn)}")
    for label, subset in (
        ("  价跌+OI跌(撤风险)", [r for r in dn if r["p_chg"] < 0]),
        ("  价涨+OI跌(空头回补)", [r for r in dn if r["p_chg"] >= 0]),
    ):
        for h in (1, 3, 5):
            print(f"{label} {fw(subset, f'fwd{h}')}")
    up = [
        r
        for r in all_days
        if r["oi_chg"] is not None and r["p_chg"] is not None and r["oi_chg"] > 0.02
    ]
    print(f"  对照 OI单日涨>2% {fw(up, 'fwd3')}")

    print("\n=== 深回撤(dd>=10%)内部再按当日价格方向切分 ===")
    d10p = [r for r in d10 if r["p_chg"] is not None]
    for label, subset in (
        ("  dd>=10% 且当日价跌", [r for r in d10p if r["p_chg"] < 0]),
        ("  dd>=10% 且当日价涨", [r for r in d10p if r["p_chg"] >= 0]),
    ):
        for h in (1, 3, 5):
            print(f"{label} {fw(subset, f'fwd{h}')}")

    # ================= 反向分析: 大跌前夜长什么样 =================
    BIG = -0.15
    base5 = [r for r in all_days if r["fwd5"] is not None]
    big = [r for r in base5 if r["fwd5"] <= BIG]
    print(f"\n=== 反向分析: 大跌(5日<= {BIG:.0%}) n={len(big)} / {len(base5)} "
          f"(基准率 {len(big)/len(base5):.1%}) ===")

    def profile(label, records):
        oh = [r["off_high"] for r in records if r["off_high"] is not None]
        dsh = [r["days_since_high"] for r in records if r["days_since_high"] is not None]
        dd_ = [r["dd"] for r in records]
        o3 = [r["oi_chg3"] for r in records if r["oi_chg3"] is not None]
        pc = [r["p_chg"] for r in records if r["p_chg"] is not None]
        print(
            f"{label} 距30日价高: p50={quantile(oh, 0.5):+.1%} | "
            f"距价高天数: p50={quantile(dsh, 0.5):.0f} | OI dd: p50={quantile(dd_, 0.5):.1%} | "
            f"3日OI变化: p50={quantile(o3, 0.5):+.1%} | 当日价变: p50={quantile(pc, 0.5):+.1%}"
        )

    profile("  大跌前夜", big)
    profile("  普通日  ", [r for r in base5 if r["fwd5"] > BIG])

    print("\n--- 各候选条件对大跌的捕获率(recall)与条件下大跌率(precision) ---")
    conds = [
        ("价距30日高<3%(贴顶)", lambda r: r["off_high"] is not None and r["off_high"] > -0.03),
        ("价距30日高>15%(已崩段)", lambda r: r["off_high"] is not None and r["off_high"] <= -0.15),
        ("OI dd>=10%", lambda r: r["dd"] >= 0.10),
        ("OI dd<10%(OI仍在高位)", lambda r: r["dd"] < 0.10),
        ("3日OI增>10%(杠杆急堆)", lambda r: r["oi_chg3"] is not None and r["oi_chg3"] > 0.10),
        ("贴顶 且 3日OI增>10%", lambda r: r["off_high"] is not None and r["off_high"] > -0.03
            and r["oi_chg3"] is not None and r["oi_chg3"] > 0.10),
        ("贴顶 且 OI dd>=10%", lambda r: r["off_high"] is not None and r["off_high"] > -0.03
            and r["dd"] >= 0.10),
        ("当日价跌 且 OI dd>=10%", lambda r: r["p_chg"] is not None and r["p_chg"] < 0
            and r["dd"] >= 0.10),
    ]
    for name, f in conds:
        hit = [r for r in base5 if f(r)]
        n_big = sum(1 for r in hit if r["fwd5"] <= BIG)
        recall = sum(1 for r in big if f(r)) / len(big) if big else 0
        prec = n_big / len(hit) if hit else 0
        med = quantile([r["fwd5"] for r in hit], 0.5) if hit else float("nan")
        print(
            f"  {name}: 命中n={len(hit)} 大跌率={prec:.1%} 捕获率={recall:.0%} 5日中位={med:+.2%}"
        )

    print("\n--- BD顶后第N天入场对照(A=现行价量双高池 / H=切比堆积非天量池) ---")
    for pool_tag in ("A", "H"):
        for lag in range(1, 6):
            sub = [
                r
                for r in all_lags
                if r["pool"] == pool_tag and r["lag"] == lag and r["fwd3"] is not None
            ]
            if sub:
                n_dd = sum(1 for r in sub if r["dd"] >= 0.10)
                print(
                    f"  [{pool_tag}]顶后第{lag}天: {fw(sub, 'fwd3')} | 当日dd>=10%占比 {n_dd/len(sub):.0%}"
                )
        for lag in range(1, 6):
            sub = [
                r
                for r in all_lags
                if r["pool"] == pool_tag
                and r["lag"] == lag
                and r["fwd3"] is not None
                and r["dd"] >= 0.10
            ]
            if sub:
                print(f"  [{pool_tag}]顶后第{lag}天且dd>=10%: {fw(sub, 'fwd3')}")

    # ============ 入池来源对照: 扣扳机统一为顶后3-5天首个dd>=10%日 ============
    print("\n=== 入池来源对照(扣扳机统一: 顶后第3-5天首个OI dd>=10%日入场) ===")
    if chain_total:
        print(
            f"链条验证: BZ型日(价涨+量10日高+OI日增>={BZ_OI_DAY_SURGE:.0%}) 共{chain_total}个, "
            f"其后0-3天内出现30日价格新高的占 {chain_hits/chain_total:.0%}"
        )
    for name in sorted(all_pools):
        evs = all_pools[name]
        print(f"  [{name}] 入池顶数={all_pool_anchors.get(name, 0)} 触发入场={len(evs)}")
        for h in (1, 3, 5):
            print(f"    {fw(evs, f'fwd{h}')}")

    print("\n--- 成本位假说: 按'锚日距30日量峰天数'切分(池=价高+切比<5%, 全窗扣扳机) ---")
    jj = [e for e in all_pools.get("J 价高+切比<5%(不排量,全窗)", []) if e["vpk"] is not None]
    for lo, hi, label in ((0, 0, "量峰=当日 "), (1, 2, "量峰1-2天前"), (3, 7, "量峰3-7天前"), (8, 99, "量峰>7天前")):
        sub = [e for e in jj if lo <= e["vpk"] <= hi]
        if sub:
            print(f"  {label} n={len(sub)}: {fw(sub, 'fwd3')}")
    print(f"  全体距量峰天数 p50={quantile([e['vpk'] for e in jj], 0.5):.0f}" if jj else "")


if __name__ == "__main__":
    asyncio.run(main())
