---
doc_type: issue-fix
issue: 2026-07-26-bz-close-preserve-observation
status: completed
date: 2026-07-26
severity: P1
tags: [autobn, bz, observation, cooldown, timestamp]
---

# BZ完整平仓保留Observation修复记录

## 问题与根因

AUTOBN完整平仓处理无条件删除Observation，使BZ原观察无法保留至其原始24小时有效期结束。根因位于 `tokenDemo/autoTrade_pm.py:_handle_closed_position_observation`：BZ与BD未按策略区分。

## 修复

- BD确认完整平仓继续删除Observation。
- BZ确认完整平仓保留现有Observation，只把 `earliest_open_timestamp` 设置为确认清仓时间加重开冷却。
- BZ的 `timestamp`、价格、策略等其他字段保持不变，让记录继续按原始观察时间自然过期。
- Observation缺失时不补造；部分平仓、查询失败或仍有余仓时保持原样。
- 同步修订共享Observation生命周期Requirement。

## 验证

- 覆盖下单前已确认归零、下单后确认归零、异常恢复确认归零、已过期但尚待常规清理、Observation缺失和BD完整平仓。
- 部分BD平仓保持Observation不变的既有测试继续通过。
- `uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py`：通过。
- `uv run python -m unittest tokenDemo.test_autoTrade_pm`：86项测试通过，结果 `OK`。

## 范围

仅修改 `tokenDemo/autoTrade_pm.py`、`tokenDemo/test_autoTrade_pm.py`、共享Observation Requirement和本fix-note；未带入其他工作区改动。
