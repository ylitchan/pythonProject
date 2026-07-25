---
doc_type: feature-ff-note
feature: redesign-bd-short-signal
date: 2026-07-25
requirement:
tags: [autobn, short-signal, open-interest, chebyshev]
---

## 做了什么

按 `calibrate-short-oi-drawdown` 的数据结论重做 AUTOBN 的 BD 做空信号（v3）。

- **入池**（原：近 3 天价量双创新高）→ 当日价创 30 日新高 ＋ 近 10 日 `max(oi_1d)` 对前 20 日基线切比雪夫 <5%（顶部堆积极端多头杠杆＝清算燃料）＋ **量峰距今 ≥3 天**（原"必须天量"翻转为"必须避开新鲜资金成本位"）。
- **扣扳机**（原：`oi_5m ≤ min(30日 oi_1d)` ＋ 空头切比雪夫，实测 8443 样本日 0 次成立＝等于关闸）→ `oi_5m ≤ max(oi_1d) × 0.90`，确认堆积的杠杆正在被清算。
- **观察期** 24h → 5 天，覆盖顶后清算的第二腿展开期（大跌多在顶后 3-5 天，不在首日）。
- 每日刷新观察记录的机制按用户决定保留不动（条件持续成立就续期是合理的）。

数据依据：改进池"价高+切比 <5%+量峰 ≥3 天"在本月 27 个顶中 8 次触发，3 日中位 **-10.43% / 80% 下跌**，是全部 10 组对照中唯一 1 日与 3 日均值中位全负的形态。

## 改了哪些

- tokenDemo/autoTrade_pm.py:296 — `OBSERVATION_TIMEOUT_SECONDS` 24h → 5 天
- tokenDemo/autoTrade_pm.py:335-340 — 新增 `SHORT_OI_CHEB_THRESHOLD=0.05`、`BD_OI_PEAK_LOOKBACK=10`、`BD_VOLUME_PEAK_MIN_AGE=3`、`BD_OI_DRAWDOWN_RATIO=0.1`
- tokenDemo/autoTrade_pm.py:1065 `_get_oi_1d_data` — 从 `check_side` 内联缓存逻辑抽成方法，供入池判定复用（同日只打一次 API）
- tokenDemo/autoTrade_pm.py:1101-1117 `check_side` SHORT 分支 — `≤min` ＋切比雪夫改为峰值回撤 10%
- tokenDemo/autoTrade_pm.py:1912 `_is_bd_observation` — 新增入池三条件判定
- tokenDemo/autoTrade_pm.py:2174 `rzq_token` — BD 分支改调 `_is_bd_observation`
- tokenDemo/test_autoTrade_pm.py:876 `AutoBNShortSignalTest` — 新增 7 个用例（三条件各自否决 / 三条件齐备通过 / OI 数据缺失 / 回撤阈值边界 True-False 两侧）

## 怎么验证的

`uv run python -m unittest tokenDemo.test_autoTrade_pm` 53 个测试全部通过（原 46 + 新增 7）。入池的价格腿与量峰腿在 OI 请求之前短路，测试断言 `_get_oi_1d_data` 未被调用，确认没有多余 API 开销。

## 顺手发现（可选，不阻塞）

- 结论基于单月横截面（Binance OI 仅留 30 天）、且本月为动量强市，方向可信、绝对阈值待异月复核；建议留着 `tokenDemo/calibrate_short_oi_drawdown.py` 定期重跑
- 日线代理挡不住盘中逼空，入场首日均值仍有正尾（少数暴力逼空），依赖 ATR 止损截断
