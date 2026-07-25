---
doc_type: feature-ff-note
feature: unify-kline-limit-30
date: 2026-07-25
requirement:
tags: [autobn, kline, observation-window]
---

## 做了什么

AUTOBN 的 `KLINE_LIMIT` 从 96 改为 30，与 AUTOA 实际消费的 30 根日K对齐。唯一受影响的策略语义是 BD 空头观察条件：`max(close[-3:]) ≥ max(全窗口)` 的窗口从"96 日最高"收窄为"30 日最高"，BD 入池不再要求近一个季度的绝对高点，只要求近一个月高点，观察触发会更频繁。BZ（10 日量最大）、ATR(10)、MIN_KLINE_FOR_ANALYSIS(4) 均远小于 30，不受影响。AUTOA 无需改动（TRADING_DAYS_LOOKBACK=60 是抓取余量，防停牌导致有效根数不足，保留）。

## 改了哪些

- tokenDemo/autoTrade_pm.py:301 — `KLINE_LIMIT = 96` → `30`，注释标明与 AUTOA 对齐

## 怎么验证的

`uv run python -m py_compile` 编译通过；`uv run python -m unittest tokenDemo.test_autoTrade_pm` 46 个测试全部通过（测试无 96 硬编码依赖）。

## 顺手发现（可选，不阻塞）

- tokenDemo/autoTrade_pm.py:1932 — 注释"获取日K线数据（30天）"在 96 时代与代码不符，本次改动后反而变准确了，无需再改
