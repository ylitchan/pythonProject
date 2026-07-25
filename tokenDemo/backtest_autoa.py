"""AUTOA 两种入场策略回测.

复刻 autoTrade_pm.py 中 AUTOA 的完整交易逻辑, 在 A 股日线历史上回测:
  BZ 分支: 涨停入观察池后, 今开 > 昨高 + 量创 10 日新高 + 量对 [-30:-10] 基线切比雪夫 <1%
  N  分支: 已有 BZ 标签后, 昨日最低 < BZ 基准高点 且 今开 > 昨高 -> 再次入场

关键实盘细节(已复刻):
  - on_positions 每分钟跑一次(9:30-14:59 约 330 次/日), 止盈缝隙每次 ×0.999
    -> 单日缩水约 28%, 是这套系统最强的行为驱动
  - DCA 在同一分钟内会连续触发直到 price >= entry-atr 不再成立
  - N 标签仓位豁免成交量止损
  - 观察记录在开仓后不删除, 平仓后可再次入场

数据源: 新浪 stock_zh_a_daily(全历史 + 前复权); 东财涨停池只留最近 ~15 个交易日,
故涨停池用不复权日线重建(收盘=最高 且 涨幅达板), 可用 --validate-zt 对齐真值.

用法:
  PYTHONIOENCODING=utf-8 uv run python tokenDemo/backtest_autoa.py --fetch
  PYTHONIOENCODING=utf-8 uv run python tokenDemo/backtest_autoa.py --validate-zt
  PYTHONIOENCODING=utf-8 uv run python tokenDemo/backtest_autoa.py
"""

import argparse
import datetime
import os
import pickle
import socket
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import akshare as ak
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

# ==================== 回测区间与数据 ====================
START_DATE = "20190101"
END_DATE = "20260724"
SIM_START = 20200101
FETCH_WORKERS = 20
FETCH_RETRY = 4
SOCKET_TIMEOUT_SECONDS = 20
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".backtest_cache")

# ==================== 策略常量(与 AUTOA 逐个对齐) ====================
ATR_PERIOD = 10
ATR_HL2_CAP_RATIO = 0.1
ATR_TRIGGER_CAP_RATIO = 0.10
MIN_ATR_TRIGGER = 1e-8
DCA_TP_ATR_RATIO = 0.5
CHEBYSHEV_EXTREME_THRESHOLD = 0.01
OBSERVATION_TIMEOUT_DAYS = 30
SUPERTREND_FACTOR = 3.0
STOP_LOSS_DECAY = 0.001
TRAILING_STOP_PROFIT_RATIO = 0.7
TARGET_PROFIT_DIVISOR = 3.0
DEFAULT_POSITION_SHARES = 100
VOL_SAMPLE_LEN = 20  # hist_volume[-30:-10]
VOL_SAMPLE_LAG = 10  # 样本尾端距今 10 根
VOL_MAX_LEN = 10  # max(hist_volume[-10:])
HIST_ROWS = 60  # TRADING_DAYS_LOOKBACK

# on_positions 每分钟一次: 09:30-09:59 + 10:00-14:59(15 点走涨停池分支, 不做持仓)
CALLS_PER_DAY = 330
INTRADAY_NODES = 4
DECAY_PER_NODE = (1 - STOP_LOSS_DECAY) ** (CALLS_PER_DAY / INTRADAY_NODES)
# 切比雪夫 upper<0.01 <=> k>10 <=> |v-mean| > 10*std
CHEB_K = (1.0 / CHEBYSHEV_EXTREME_THRESHOLD) ** 0.5


def sina_symbol(code: str) -> str:
    return ("sh" if code[0] == "6" else "sz") + code


def board_limit(code: str) -> float:
    return 0.20 if code.startswith(("300", "301", "688")) else 0.10


# ==================== 数据拉取与缓存 ====================
def fetch_universe():
    """沪深 A 股在册清单.

    注意: 只含当前在册标的, 退市股缺失 -> 存在生存者偏差(结论会偏乐观).
    不用 ak.stock_info_a_code_name(), 它内部会打北交所接口且经常超时.
    """
    codes = set()
    try:
        codes |= set(ak.stock_info_sh_name_code()["证券代码"].astype(str))
    except Exception as e:
        print(f"  沪市清单失败: {type(e).__name__}")
    for board in ("A股列表", "主板A股"):
        try:
            df = ak.stock_info_sz_name_code(symbol=board)
            col = "A股代码" if "A股代码" in df.columns else df.columns[1]
            codes |= {str(c).zfill(6) for c in df[col] if str(c).strip().isdigit()}
            break
        except Exception as e:
            print(f"  深市清单({board})失败: {type(e).__name__}")
    return sorted(c for c in codes if len(c) == 6 and not c.startswith(("4", "8", "9")))


def _fetch_one(code, adjust):
    sym = sina_symbol(code)
    for _ in range(FETCH_RETRY):
        try:
            df = ak.stock_zh_a_daily(
                symbol=sym, start_date=START_DATE, end_date=END_DATE, adjust=adjust
            )
            if df is not None and not df.empty:
                return code, df[["date", "open", "high", "low", "close", "volume"]]
        except Exception:
            time.sleep(1.0)
    return code, None


def fetch_all(adjust, tag):
    path = os.path.join(CACHE_DIR, f"bars_{tag}.pkl")
    partial_path = os.path.join(CACHE_DIR, f"bars_{tag}.partial.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    os.makedirs(CACHE_DIR, exist_ok=True)
    socket.setdefaulttimeout(SOCKET_TIMEOUT_SECONDS)
    codes = fetch_universe()
    out = {}
    if os.path.exists(partial_path):
        with open(partial_path, "rb") as f:
            out = pickle.load(f)
    remaining = [code for code in codes if code not in out]
    print(
        f"拉取 {tag} 日线: 总计{len(codes)} 已缓存{len(out)} 待拉{len(remaining)}只",
        flush=True,
    )
    done, t0 = 0, time.time()
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
        futures = [ex.submit(_fetch_one, code, adjust) for code in remaining]
        for future in as_completed(futures):
            code, df = future.result()
            done += 1
            if df is not None:
                out[code] = df
            if done % 200 == 0:
                with open(partial_path, "wb") as f:
                    pickle.dump(out, f)
                print(
                    f"  {done}/{len(remaining)} 成功累计{len(out)} "
                    f"耗时{time.time() - t0:.0f}s",
                    flush=True,
                )
    print(f"{tag} 完成: {len(out)}/{len(codes)} 耗时{time.time() - t0:.0f}s")
    with open(path, "wb") as f:
        pickle.dump(out, f)
    if os.path.exists(partial_path):
        os.remove(partial_path)
    return out


def to_int_dates(series):
    return np.array([int(str(d).replace("-", "")[:8]) for d in series], dtype=np.int64)


# ==================== 向量化预计算 ====================
def roll_max(a, w):
    """out[i] = max(a[i-w+1..i]), 不足处为 nan."""
    out = np.full(len(a), np.nan)
    if len(a) >= w:
        out[w - 1 :] = sliding_window_view(a, w).max(axis=1)
    return out


def roll_mean_std(a, w, lag):
    """样本窗口 a[i-w-lag+1 .. i-lag], 返回 (mean, std ddof=1)."""
    n = len(a)
    mean, std = np.full(n, np.nan), np.full(n, np.nan)
    if n >= w + lag:
        win = sliding_window_view(a, w)  # win[j] 覆盖 a[j..j+w-1]
        m, s = win.mean(axis=1), win.std(axis=1, ddof=1)
        idx = np.arange(w + lag - 1, n)  # 窗口尾端 = i-lag -> j = i-lag-w+1
        mean[idx], std[idx] = m[idx - lag - w + 1], s[idx - lag - w + 1]
    return mean, std


def precompute(s):
    o, h, low, c, v = s["o"], s["h"], s["l"], s["c"], s["v"]
    n = len(c)
    tr = np.full(n, np.nan)
    tr[1:] = np.maximum(
        h[1:] - low[1:],
        np.maximum(np.abs(h[1:] - c[:-1]), np.abs(low[1:] - c[:-1])),
    )
    # ATR: 末 10 根 TR 简单均值(非 Wilder), 上限 hl2*10%
    atr_raw = np.full(n, np.nan)
    if n >= ATR_PERIOD + 1:
        atr_raw[ATR_PERIOD:] = (
            sliding_window_view(tr[1:], ATR_PERIOD).sum(axis=1) / ATR_PERIOD
        )
    hl2 = (h + low) / 2
    s["atr"] = np.minimum(atr_raw, np.where(hl2 > 0, hl2 * ATR_HL2_CAP_RATIO, atr_raw))
    # 持仓端要用盘中实时末根 TR 替换 -> 预存前 9 根之和
    tr_sum9 = np.full(n, np.nan)
    if n >= ATR_PERIOD:
        tr_sum9[ATR_PERIOD - 1 :] = sliding_window_view(tr[1:], ATR_PERIOD - 1).sum(axis=1)
    s["tr_sum9"] = tr_sum9

    s["bull"] = c > o
    gap = np.zeros(n, dtype=bool)
    gap[1:] = o[1:] > h[:-1]
    s["gap_up"] = gap
    s["vmax10"] = v >= roll_max(v, VOL_MAX_LEN)
    vm, vs = roll_mean_std(v, VOL_SAMPLE_LEN, VOL_SAMPLE_LAG)
    s["vol_mean"], s["vol_std"] = vm, vs
    with np.errstate(invalid="ignore"):
        s["cheb_ok"] = (vs == 0) | (np.abs(v - vm) > CHEB_K * vs)
    return s


def build_dataset():
    qfq = fetch_all("qfq", "qfq")
    raw = fetch_all("", "raw")
    stocks, zt_by_date = {}, {}
    for code, dq in qfq.items():
        dr = raw.get(code)
        if dr is None or len(dq) < HIST_ROWS + 2:
            continue
        dates_q, dates_r = to_int_dates(dq["date"]), to_int_dates(dr["date"])
        if not np.array_equal(dates_q, dates_r):
            common, iq, ir = np.intersect1d(dates_q, dates_r, return_indices=True)
            if len(common) < HIST_ROWS + 2:
                continue
            dq, dr, dates_q = dq.iloc[iq], dr.iloc[ir], common
        c_raw = dr["close"].to_numpy(dtype=np.float64)
        h_raw = dr["high"].to_numpy(dtype=np.float64)
        prev = np.concatenate([[np.nan], c_raw[:-1]])
        with np.errstate(invalid="ignore", divide="ignore"):
            pct = c_raw / prev - 1
        lim = board_limit(code)
        limit_up = (pct >= lim - 0.003) & (c_raw >= h_raw - 1e-9) & np.isfinite(pct)
        stocks[code] = precompute(
            {
                "dates": dates_q,
                "o": dq["open"].to_numpy(dtype=np.float64),
                "h": dq["high"].to_numpy(dtype=np.float64),
                "l": dq["low"].to_numpy(dtype=np.float64),
                "c": dq["close"].to_numpy(dtype=np.float64),
                "v": dq["volume"].to_numpy(dtype=np.float64),
                "idx": {int(d): i for i, d in enumerate(dates_q)},
            }
        )
        for i in np.flatnonzero(limit_up):
            zt_by_date.setdefault(int(dates_q[i]), []).append(code)
    return stocks, zt_by_date


def ordinal(d):
    return datetime.date(d // 10000, (d // 100) % 100, d % 100).toordinal()


# ==================== 回测 ====================
class Position:
    __slots__ = (
        "code", "entry_price", "first_entry", "take_profit", "stop_loss",
        "entry_date", "branch", "strategy", "guard", "close_reason",
        "shares", "cost", "dca_count",
    )


class Observation:
    __slots__ = ("obs_date", "strategy", "bz_ref")


def new_observation(today):
    ob = Observation()
    ob.obs_date, ob.strategy, ob.bz_ref = today, [], None
    return ob


class Backtest:
    def __init__(self, stocks, zt_by_date, high_first=False, enable_n=True,
                 enable_dca=True, enable_vol_stop=True):
        self.stocks = stocks
        self.zt_by_date = zt_by_date
        self.high_first = high_first
        self.enable_n = enable_n
        self.enable_dca = enable_dca
        self.enable_vol_stop = enable_vol_stop
        self.obs, self.pos, self.trades = {}, {}, []
        self.n_entries = {"BZ": 0, "N": 0}

    # ---------- on_observations ----------
    def on_observation(self, code, di, today, today_ord):
        ob = self.obs[code]
        if today_ord - ordinal(ob.obs_date) > OBSERVATION_TIMEOUT_DAYS:
            del self.obs[code]
            return
        if today == ob.obs_date or di < HIST_ROWS - 1:
            return
        s = self.stocks[code]
        if not s["bull"][di] or not s["gap_up"][di]:
            return
        if np.isnan(s["vol_std"][di]):  # 等价于 len(hist_volume) < 30
            return

        if s["vmax10"][di] and s["cheb_ok"][di]:
            ob.bz_ref = float(s["h"][di - 1])
            if "BZ" not in ob.strategy:
                ob.strategy.append("BZ")
            branch = "BZ"
        elif (
            self.enable_n
            and "BZ" in ob.strategy
            and ob.bz_ref
            and s["l"][di - 1] < ob.bz_ref
        ):
            if "N" not in ob.strategy:
                ob.strategy.append("N")
            branch = "N"
        else:
            return

        atr = float(s["atr"][di])
        if not atr > 0:
            return
        hl2 = (s["h"][di] + s["l"][di]) / 2
        p = Position()
        p.code = code
        p.entry_price = p.first_entry = float(s["c"][di])
        p.take_profit = hl2 + atr * SUPERTREND_FACTOR
        p.stop_loss = hl2 - atr * SUPERTREND_FACTOR
        p.entry_date, p.branch = today, branch
        p.strategy = list(ob.strategy)
        p.guard = float(s["vol_mean"][di])
        p.close_reason = ""
        p.shares = DEFAULT_POSITION_SHARES
        p.cost = p.entry_price * DEFAULT_POSITION_SHARES
        p.dca_count = 0
        self.pos[code] = p
        self.n_entries[branch] += 1

    # ---------- on_positions (4 节点盘中路径) ----------
    def on_position(self, code, di, today):
        p = self.pos[code]
        if today <= p.entry_date or di < 1:
            return
        s = self.stocks[code]
        o, hi, lo, cl = (float(s[k][di]) for k in ("o", "h", "l", "c"))
        prev_close = float(s["c"][di - 1])
        tr_sum9 = s["tr_sum9"][di - 1]
        prev_volume = float(s["v"][di - 1])
        vol_stop_armed = (
            self.enable_vol_stop
            and "N" not in p.strategy
            and p.guard > 0
            and 0 < prev_volume <= p.guard
        )

        path = [o, hi, lo, cl] if self.high_first else [o, lo, hi, cl]
        run_hi = run_lo = o
        for node, price in enumerate(path):
            run_hi, run_lo = max(run_hi, price), min(run_lo, price)
            gap_node = node == 0  # 开盘可能直接跳过价位 -> 按开盘价成交

            if price >= p.take_profit:
                self.close(p, max(p.take_profit, o) if gap_node else p.take_profit,
                           today, "止盈")
                return
            if price <= p.stop_loss:
                self.close(p, min(p.stop_loss, o) if gap_node else p.stop_loss,
                           today, p.close_reason or "初始止损")
                return
            if vol_stop_armed:
                self.close(p, price, today, "成交量止损")
                return

            atr = self._atr_at(tr_sum9, run_hi, run_lo, prev_close)
            hl2 = (run_hi + run_lo) / 2
            upper, lower = hl2 + atr * SUPERTREND_FACTOR, hl2 - atr * SUPERTREND_FACTOR

            # DCA: 实盘每分钟复查, 同一价位会连续加到条件不成立
            dca_hit = False
            while (
                self.enable_dca
                and atr > 0
                and p.entry_price > 0
                and price < p.entry_price - atr
                and p.dca_count < 50
            ):
                level = p.entry_price - atr
                fill = min(level, o) if gap_node else level
                p.shares += DEFAULT_POSITION_SHARES
                p.cost += fill * DEFAULT_POSITION_SHARES
                p.entry_price = p.cost / p.shares
                p.dca_count += 1
                p.strategy.append("DCA")
                p.take_profit = min(
                    p.take_profit, p.entry_price + atr * DCA_TP_ATR_RATIO**p.dca_count
                )
                dca_hit = True
            if dca_hit:
                continue

            gap = p.take_profit - p.entry_price
            decayed = p.entry_price + gap * DECAY_PER_NODE
            if p.dca_count > 0:
                dca_tp = p.entry_price + atr * DCA_TP_ATR_RATIO**p.dca_count
                p.take_profit = max(min(decayed, upper, dca_tp), p.entry_price)
            else:
                p.take_profit = max(min(decayed, upper), p.entry_price)

            profit = price - p.entry_price
            atr_trigger = max(
                min(atr, p.entry_price * ATR_TRIGGER_CAP_RATIO), MIN_ATR_TRIGGER
            )
            target = min(gap / TARGET_PROFIT_DIVISOR, atr_trigger)
            if profit >= target:
                trailing = p.entry_price + profit * TRAILING_STOP_PROFIT_RATIO
                if trailing > p.stop_loss:
                    p.stop_loss = trailing
                    p.close_reason = "追踪止损(保护盈利)"
            elif lower > p.stop_loss:
                p.stop_loss = lower
                p.close_reason = "移动止损(轨道)"

    @staticmethod
    def _atr_at(tr_sum9, run_hi, run_lo, prev_close):
        if np.isnan(tr_sum9):
            return 0.0
        tr_last = max(run_hi - run_lo, abs(run_hi - prev_close), abs(run_lo - prev_close))
        atr = (float(tr_sum9) + tr_last) / ATR_PERIOD
        cap = (run_hi + run_lo) / 2 * ATR_HL2_CAP_RATIO
        return min(atr, cap) if cap > 0 else atr

    def close(self, p, price, today, reason):
        del self.pos[p.code]
        self.trades.append(
            {
                "code": p.code,
                "branch": p.branch,
                "entry_date": p.entry_date,
                "exit_date": today,
                "entry_price": p.entry_price,
                "first_entry": p.first_entry,
                "exit_price": price,
                "ret": price / p.entry_price - 1,
                "pnl": (price - p.entry_price) * p.shares,
                "cost": p.cost,
                "dca": p.dca_count,
                "reason": reason,
                "hold": None,
            }
        )

    def run(self, all_dates):
        dpos = {d: i for i, d in enumerate(all_dates)}
        for today in all_dates:
            if today >= SIM_START:
                t_ord = ordinal(today)
                for code in list(self.pos):
                    di = self.stocks[code]["idx"].get(today)
                    if di is not None:  # None = 停牌, 实盘当日拿不到数据
                        self.on_position(code, di, today)
                for code in list(self.obs):
                    if code in self.pos:
                        continue
                    di = self.stocks[code]["idx"].get(today)
                    if di is None:
                        if t_ord - ordinal(self.obs[code].obs_date) > OBSERVATION_TIMEOUT_DAYS:
                            del self.obs[code]
                        continue
                    self.on_observation(code, di, today, t_ord)
            for code in self.zt_by_date.get(today, ()):  # 15:00 涨停池入观察
                if code in self.obs:
                    self.obs[code].obs_date = today
                else:
                    self.obs[code] = new_observation(today)

        last = all_dates[-1]
        for code in list(self.pos):
            s = self.stocks[code]
            di = s["idx"].get(last, len(s["c"]) - 1)
            self.close(self.pos[code], float(s["c"][di]), last, "回测截止未平")
        for t in self.trades:
            a, b = dpos.get(t["entry_date"]), dpos.get(t["exit_date"])
            t["hold"] = (b - a) if (a is not None and b is not None) else None
        return self.trades


# ==================== 统计输出 ====================
def q(vals, p):
    s = sorted(vals)
    if not s:
        return float("nan")
    x = p * (len(s) - 1)
    i = int(x)
    j = min(i + 1, len(s) - 1)
    return s[i] + (s[j] - s[i]) * (x - i)


def pf(x):
    return f"{x:+.2%}"


def describe(name, trades, total_n=None):
    print(f"\n=== {name} ===")
    if not trades:
        print("无交易")
        return
    rets = [t["ret"] for t in trades]
    pnls = [t["pnl"] for t in trades]
    costs = [t["cost"] for t in trades]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    gw = sum(x for x in pnls if x > 0)
    gl = -sum(x for x in pnls if x <= 0)
    holds = [t["hold"] for t in trades if t["hold"] is not None]
    share = f" (占全部 {len(trades) / total_n:.1%})" if total_n else ""
    pr = f"{gw / gl:.2f}" if gl > 0 else "inf"
    print(f"交易数={len(trades)}{share}  胜率={len(wins) / len(trades):.1%}")
    print(
        f"平均收益={pf(statistics.mean(rets))}  中位={pf(q(rets, 0.5))}  "
        f"平均盈利={pf(statistics.mean(wins)) if wins else 'n/a'}  "
        f"平均亏损={pf(statistics.mean(losses)) if losses else 'n/a'}  盈亏比={pr}"
    )
    print(
        f"总盈亏={sum(pnls):,.0f} CNY  总投入={sum(costs):,.0f} CNY  "
        f"资金加权={sum(pnls) / sum(costs):+.2%}"
    )
    if holds:
        print(
            f"持仓天数: 均值={statistics.mean(holds):.1f} 中位={q(holds, 0.5):.0f} "
            f"p90={q(holds, 0.9):.0f} 最大={max(holds)}"
        )
    print(
        f"收益分位: p5={pf(q(rets, 0.05))} p25={pf(q(rets, 0.25))} "
        f"p75={pf(q(rets, 0.75))} p95={pf(q(rets, 0.95))} "
        f"最差={pf(min(rets))} 最好={pf(max(rets))}"
    )
    reasons = {}
    for t in trades:
        reasons.setdefault(t["reason"], []).append(t["ret"])
    print("平仓依据:")
    for r, vals in sorted(reasons.items(), key=lambda kv: -len(kv[1])):
        print(
            f"  {r:<18} n={len(vals):<6} 占比={len(vals) / len(trades):>6.1%} "
            f"平均={pf(statistics.mean(vals))} 中位={pf(q(vals, 0.5))}"
        )
    used = [t for t in trades if t["dca"] > 0]
    nod = [t for t in trades if t["dca"] == 0]
    if used:
        print(
            f"DCA: 触发 n={len(used)} ({len(used) / len(trades):.1%}) "
            f"平均={pf(statistics.mean([t['ret'] for t in used]))} "
            f"平均加仓次数={statistics.mean([t['dca'] for t in used]):.1f} | "
            f"未触发 n={len(nod)} 平均="
            f"{pf(statistics.mean([t['ret'] for t in nod])) if nod else 'n/a'}"
        )
    by_year = {}
    for t in trades:
        by_year.setdefault(t["exit_date"] // 10000, []).append(t)
    print("分年度(按平仓年):")
    for y in sorted(by_year):
        sub = by_year[y]
        yr = [t["ret"] for t in sub]
        print(
            f"  {y}: n={len(sub):<6} 胜率={sum(1 for r in yr if r > 0) / len(yr):>6.1%} "
            f"平均={pf(statistics.mean(yr))} 中位={pf(q(yr, 0.5))} "
            f"盈亏={sum(t['pnl'] for t in sub):>12,.0f}"
        )


def report(tag, bt, trades):
    print(
        f"\n{'#' * 72}\n# {tag}\n"
        f"# 入场次数: BZ={bt.n_entries['BZ']} N={bt.n_entries['N']}\n{'#' * 72}"
    )
    describe("全部交易", trades)
    describe("BZ 分支(放量跳空首入)", [t for t in trades if t["branch"] == "BZ"], len(trades))
    describe("N 分支(回踩后再跳空)", [t for t in trades if t["branch"] == "N"], len(trades))


def validate_zt(stocks, zt_by_date):
    print("=== 涨停池重建校验(对比东财 stock_zt_pool_em) ===")
    checked = 0
    for probe in range(0, 45):
        d = 20260724 - probe
        try:
            df = ak.stock_zt_pool_em(date=str(d))
        except Exception:
            continue
        if df is None or df.empty:
            continue
        truth = {c for c in df["代码"].astype(str) if not c.startswith(("4", "8", "9"))}
        truth &= set(stocks)  # 只比可比范围
        mine = set(zt_by_date.get(d, ()))
        if not truth or not mine:
            continue
        inter = truth & mine
        print(
            f"  {d}: 真值{len(truth)} 重建{len(mine)} 交集{len(inter)} "
            f"召回={len(inter) / len(truth):.1%} 精确={len(inter) / len(mine):.1%}"
        )
        checked += 1
        if checked >= 8:
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--validate-zt", action="store_true")
    ap.add_argument("--ablation", action="store_true", help="额外跑消融实验")
    args = ap.parse_args()

    if args.fetch:
        fetch_all("qfq", "qfq")
        fetch_all("", "raw")
        return

    t0 = time.time()
    stocks, zt_by_date = build_dataset()
    print(f"有效标的={len(stocks)}  载入+预计算耗时{time.time() - t0:.0f}s")
    if args.validate_zt:
        validate_zt(stocks, zt_by_date)
        return

    all_dates = sorted({int(d) for s in stocks.values() for d in s["dates"]})
    all_dates = [d for d in all_dates if d <= int(END_DATE)]
    print(
        f"交易日={len(all_dates)} 区间 {all_dates[0]}-{all_dates[-1]}  "
        f"重建涨停日={sum(len(v) for v in zt_by_date.values())}  "
        f"单日止盈缝隙衰减系数={(1 - STOP_LOSS_DECAY) ** CALLS_PER_DAY:.3f}"
    )

    t0 = time.time()
    bt = Backtest(stocks, zt_by_date, high_first=False)
    trades = bt.run(all_dates)
    print(f"\n模拟耗时{time.time() - t0:.0f}s  总交易={len(trades)}")
    report("基准(盘中路径 开-低-高-收, 偏保守)", bt, trades)

    bt2 = Backtest(stocks, zt_by_date, high_first=True)
    report("敏感性(盘中路径 开-高-低-收, 偏乐观)", bt2, bt2.run(all_dates))

    if args.ablation:
        for kw, tag in [
            ({"enable_dca": False}, "消融: 关闭 DCA"),
            ({"enable_vol_stop": False}, "消融: 关闭成交量止损"),
            ({"enable_n": False}, "消融: 只做 BZ"),
        ]:
            b = Backtest(stocks, zt_by_date, high_first=False, **kw)
            report(tag, b, b.run(all_dates))


if __name__ == "__main__":
    sys.exit(main())
