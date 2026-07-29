---
doc_type: issue-fix
issue: 2026-07-29-bd-latest-oi-breakout
status: fixed
severity: P1
summary: BD 入池的近期 OI 条件混合日线 OI 与最新 5m OI，未保证最新 OI 突破旧峰值
tags: [autobn, bd, oi]
---

# BD 最新 OI 突破条件修复

## 根因

`_get_bd_oi_windows` 返回 30 根已完成 1d OI 加最新一根 5m OI。`_is_bd_observation` 原先对 `oi_window[-3:]` 取最大值，导致较早的 1d OI 突破旧窗口峰值时，即使最新 5m OI 未突破也可通过该条件。

## 修复

- 保留 `oi_old = oi_window[-10:-3]`；该偏移已与包含当天进行中周期的日 K 成交量窗口 `[-10:-3]` 按日期对齐。
- 把近期峰值比较改为仅判断 `oi_window[-1] > max(oi_old)`，明确要求最新 5m OI 突破旧 OI 峰值。
- 增加回归测试，覆盖“较早 1d OI 已突破、最新 5m OI 未突破”必须拒绝入池的场景。

## 验证

- `uv run python -m unittest tokenDemo.test_autoTrade_pm.AutoBNShortSignalTest -q`：19 个测试通过。
- `uv run python -m unittest tokenDemo.test_autoTrade_pm -q`：118 个测试通过。
- `uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py`：通过。
