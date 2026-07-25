"""校验 backtest_autoa 的向量化预计算与 AUTOA 原始逐行实现是否等价."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest_autoa import (
    ATR_PERIOD, CHEBYSHEV_EXTREME_THRESHOLD, HIST_ROWS,
    Backtest, precompute,
)
from autoTrade_pm import AUTOA

rng = np.random.default_rng(20260725)
N = 400
close = 10 + np.cumsum(rng.normal(0, 0.3, N))
close = np.abs(close) + 1
high = close + np.abs(rng.normal(0, 0.25, N))
low = close - np.abs(rng.normal(0, 0.25, N))
open_ = low + (high - low) * rng.random(N)
vol = np.abs(rng.lognormal(12, 1.0, N))
# 注入若干极端放量, 保证 BZ 条件有机会成立
vol[[80, 150, 151, 233, 310]] *= 60

df = pd.DataFrame(
    {"open": open_, "high": high, "low": low, "close": close, "volume": vol}
)
s = precompute(
    {
        "o": open_.copy(), "h": high.copy(), "l": low.copy(),
        "c": close.copy(), "v": vol.copy(),
    }
)

# ---------- 1. ATR ----------
bad = 0
for i in range(HIST_ROWS - 1, N):
    hist = df.iloc[i - HIST_ROWS + 1 : i + 1].reset_index(drop=True)
    ref = AUTOA.calculate_atr(hist, period=ATR_PERIOD)
    mine = s["atr"][i]
    if abs(ref - mine) > 1e-9:
        bad += 1
        if bad <= 3:
            print(f"  ATR 不一致 i={i} ref={ref!r} mine={mine!r}")
print(f"ATR: 比对 {N - HIST_ROWS + 1} 点, 不一致 {bad}")

# ---------- 2. 切比雪夫 + 量能条件 ----------
bad_cheb = bad_bz = 0
for i in range(HIST_ROWS - 1, N):
    hv = vol[i - HIST_ROWS + 1 : i + 1]
    sample = hv[-30:-10]
    cur = hv[-1]
    ref_ok = (
        AUTOA.calculate_chebyshev_probability(list(sample), cur)["chebyshev_upper_bound"]
        < CHEBYSHEV_EXTREME_THRESHOLD
    )
    if bool(s["cheb_ok"][i]) != ref_ok:
        bad_cheb += 1
        if bad_cheb <= 3:
            print(f"  切比雪夫 不一致 i={i} ref={ref_ok} mine={s['cheb_ok'][i]}")
    ref_guard = float(sum(sample) / len(sample))
    if abs(ref_guard - s["vol_mean"][i]) > 1e-6:
        print(f"  guard 不一致 i={i} {ref_guard} vs {s['vol_mean'][i]}")
    # 完整 BZ 条件
    ho = open_[i - HIST_ROWS + 1 : i + 1]
    hh = high[i - HIST_ROWS + 1 : i + 1]
    ref_bz = ho[-1] > hh[-2] and cur >= max(hv[-10:]) and ref_ok
    mine_bz = bool(s["gap_up"][i] and s["vmax10"][i] and s["cheb_ok"][i])
    if ref_bz != mine_bz:
        bad_bz += 1
        if bad_bz <= 3:
            print(f"  BZ 条件 不一致 i={i} ref={ref_bz} mine={mine_bz}")
print(f"切比雪夫: 不一致 {bad_cheb}   BZ 完整条件: 不一致 {bad_bz}")
print(f"  (样本中 BZ 成立 {int(sum(s['gap_up'] & s['vmax10'] & s['cheb_ok']))} 次)")

# ---------- 3. 阳线 / gap_up ----------
ref_bull = close > open_
ref_gap = np.zeros(N, bool)
ref_gap[1:] = open_[1:] > high[:-1]
print(
    f"阳线一致={np.array_equal(ref_bull, s['bull'])}  "
    f"跳空一致={np.array_equal(ref_gap, s['gap_up'])}"
)

# ---------- 4. 持仓端 ATR(盘中末根 TR 替换) ----------
# 用完整日线时应与 calculate_atr 完全相等
bad_atr2 = 0
for i in range(HIST_ROWS, N):
    mine = Backtest._atr_at(s["tr_sum9"][i - 1], high[i], low[i], close[i - 1])
    hist = df.iloc[i - HIST_ROWS + 1 : i + 1].reset_index(drop=True)
    ref = AUTOA.calculate_atr(hist, period=ATR_PERIOD)
    if abs(ref - mine) > 1e-9:
        bad_atr2 += 1
        if bad_atr2 <= 3:
            print(f"  持仓端 ATR 不一致 i={i} ref={ref} mine={mine}")
print(f"持仓端 ATR(收盘节点应等于 calculate_atr): 不一致 {bad_atr2}")

# ---------- 5. check_gap_up_after_bz_reference ----------
bad_n = 0
for i in range(HIST_ROWS - 1, N):
    hist = df.iloc[i - HIST_ROWS + 1 : i + 1].reset_index(drop=True)
    for ref_high in (float(high[i - 3]), float(high[i - 1]), float(low[i - 1]) * 0.5):
        ref = AUTOA.check_gap_up_after_bz_reference(hist, ref_high)
        mine = bool(low[i - 1] < ref_high and s["gap_up"][i])
        if ref != mine:
            bad_n += 1
            if bad_n <= 3:
                print(f"  N 条件 不一致 i={i} ref_high={ref_high} {ref} vs {mine}")
print(f"N 条件(check_gap_up_after_bz_reference): 不一致 {bad_n}")

total_bad = bad + bad_cheb + bad_bz + bad_atr2 + bad_n
print(f"\n{'全部通过' if total_bad == 0 else f'存在 {total_bad} 处不一致'}")
