---
doc_type: feature-ff-note
feature: remove-long-lsr-extreme-conditions
date: 2026-07-25
requirement:
tags: [autobn, long-short-ratio, open-signal]
---

## 做了什么

AUTOBN check_side 多头分支去掉"多空比创回看窗口最低"（long_extreme）和"多空比 < 3/7"（long_ratio_cond）这两个二选一放行条件。保留 lsrd >= 1.0（OPEN_LONG_SHORT_RATIO_THRESHOLD）直接拒绝的硬性门槛、blend 加权多仓比例条件和 OI 极值 + 切比雪夫条件。同日早前的 remove-long-basis-gate 已去掉基差率入场门槛，两次改动后多头入场仅剩：多空比 < 1、blend >= 5m 多仓比例、5m OI 创 1h 窗口新高且切比雪夫上界 < 1%。

## 改了哪些

- tokenDemo/autoTrade_pm.py:1152-1154（check_side LONG 分支）— 删除 long_extreme / long_ratio_cond 计算及二选一放行判断
- tokenDemo/autoTrade_pm.py:309-310（类常量）— 删除因此变死代码的 LONG_SHORT_RATIO_LONG_LIMIT、LONG_SHORT_RATIO_EXTREME_LOOKBACK

## 怎么验证的

`uv run python -m py_compile` 编译通过；`uv run python -m unittest tokenDemo.test_autoTrade_pm` 46 个测试全部通过。

## 顺手发现（可选，不阻塞）

- tokenDemo/autoTrade_pm.py:310 — LONG_SHORT_RATIO_SHORT_LIMIT 在本文件无任何引用（改动前就已是死常量），autoTrade.py / autoTrade_papi.py 旧版仍在用各自的同名常量 — 不在本次范围
