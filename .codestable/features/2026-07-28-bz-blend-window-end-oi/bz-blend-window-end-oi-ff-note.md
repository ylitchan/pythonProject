---
doc_type: feature-ff-note
feature: bz-blend-window-end-oi
date: 2026-07-28
requirement:
tags: [autobn, bz, blend, open-interest]
---

## 做了什么

BZ 做多 blend 的 OI 基准从「切比雪夫区间均值」改成「该区间最后一根的 OI」。改完 blend 的两个输入（OI 和多仓比例）来自同一根 1d bar，口径自洽——之前是拿 20 天均值去配单根的比例。

取代 `2026-07-28-bz-blend-cheb-window-baseline` 里「OI 取区间均值」那一半；「多仓比例取区间末根、按时间戳定位」不变。

**止损护栏 `stop_guard_threshold` 未跟着改**，仍是区间均值——它喂的是 `_close_triggered_position` 的 OI 止损，和 blend 是两回事，本次只按要求动 blend。

## 改了哪些

- `autoTrade_pm.py:1163`（`check_side` LONG 分支）— `avg_oi_1d` → `window_end_oi = oi_hist_for_cheb[-1]`；`avg_end_long_ratio` → `window_end_long_ratio`（不再是均值，名字跟着改）。
- `autoTrade_pm.py:1194` — `stop_guard_threshold` 不再复用 blend 的中间量，独立算区间均值。
- `test_autoTrade_pm.py:1630-1750`（`AutoBNLongSignalTest`）— 夹具参数改名 `window_end_long_ratio`；`test_long_signal_blend_uses_cheb_window_avg_oi_and_ratio` 重做为 `test_long_signal_blend_uses_window_end_oi_not_window_mean`（阈值卡在 0.65 与 0.6625 之间，均值口径会被拒、末根口径放行）；两个用例加断言钉住 `stop_guard == 100.0`（区间均值）而非 105（末根）。

## 怎么验证的

`uv run ruff check` 通过；`uv run python -m unittest discover -s tokenDemo -p "test_autoTrade_pm.py"` 94 项 OK。三次反向变异各自回滚验证测试非假绿：blend 改回区间均值（挂 1）、`stop_guard` 也换成末根 OI（挂 2）、区间末根下标误取整条序列末根（挂 1）。

## 顺手发现

- 沿用上一份 ff-note 那条：1d 缓存无条件写入，跨 UTC 零点遇上币安发布延迟会把旧序列锁定一整天，应改为「末根 == 当天UTC零点」才写缓存（口径见 `compound/2026-07-28-bn-oi-lsr-only-closed-periods.md`）。不在本次范围。
