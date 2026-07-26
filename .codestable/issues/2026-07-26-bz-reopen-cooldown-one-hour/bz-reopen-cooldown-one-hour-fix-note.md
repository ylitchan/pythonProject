---
doc_type: issue-fix
issue: 2026-07-26-bz-reopen-cooldown-one-hour
status: completed
date: 2026-07-26
severity: P2
tags: [autobn, bz, observation, cooldown]
---

# BZ重开冷却调整为1小时修复记录

## 问题与根因

AUTOBN BZ确认完整平仓后仍需等待24小时才能再次开仓，与最新的1小时冷却要求不符。根因是 `tokenDemo/autoTrade_pm.py` 的 `REOPEN_COOLDOWN_SECONDS` 仍定义为24小时，并被BZ完整平仓路径用于计算最早重开时间。

## 修复

- 将AUTOBN BZ完整平仓后的重开冷却改为1小时。
- 保留原Observation且不刷新 `timestamp`；Observation仍按原始观察时间起24小时自然过期。
- BD完整平仓删除Observation、AUTOA交易日冷却及其他生命周期边界保持不变。
- 三类BZ确认归零路径和已过期待清理路径显式断言1小时冷却，避免再次与24小时有效期混淆。

## 验证

- `uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py`：通过。
- `uv run python -m unittest tokenDemo.test_autoTrade_pm`：86项测试通过，结果 `OK`。
- `git diff --check`：通过。
- 测试输出中的 `OSError: 文件被占用` 为既有错误恢复测试主动模拟的日志，不影响结果。

## 范围

仅修改 `tokenDemo/autoTrade_pm.py`、`tokenDemo/test_autoTrade_pm.py`、`.codestable/requirements/shared-observation-reopen-cooldown.md` 和本fix-note；未带入工作区其他改动，未执行commit或push。
