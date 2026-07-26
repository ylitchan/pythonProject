---
doc_type: issue-fix
issue: 2026-07-26-bz-cooldown-preserve-on-refresh
status: completed
date: 2026-07-26
severity: P1
tags: [autobn, bz, observation, cooldown, state]
---

# BZ观察刷新保留平仓冷却修复记录

## 问题与根因

AUTOBN BZ确认完整平仓时会正确写入“确认清仓时间 + 1小时”的最早重开时间，但 `rzq_token()` 同轮后续仍会执行统一的观察判定。新观察候选整条覆盖旧Observation时，未显式设置的 `earliest_open_timestamp` 会恢复为null，导致下一轮满足开仓条件后绕过冷却并立即重开。

## 修复

- 保持 `if close_info / elif open_info` 的原有职责：前者管理持仓，后者根据已有Observation决定是否开仓。
- 保持函数末尾的无条件观察段统一负责Observation新建与刷新，不增加 `else`，不改变BZ优先及新观察覆盖旧观察信号字段的规则。
- 写入新观察候选前，从写入当刻的全局Observation继承 `earliest_open_timestamp`，确保同轮平仓刚写入的冷却不会被旧局部对象或新候选默认值清空。
- AUTOA已有Observation刷新采用读取现有模型、更新观察字段后再写回的方式，正常串行流程会保留冷却，因此本次不修改AUTOA。

## 验证

- 新增同轮BZ完整平仓后再次满足观察条件时，刷新Observation仍保留1小时冷却的测试。
- 新增下一轮开仓信号成立但冷却未结束时不得调用开仓接口的测试。
- 增强旧BZ被新BD观察覆盖时仍保留生命周期冷却字段的测试。
- `uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py`：通过。
- `uv run python -m unittest tokenDemo.test_autoTrade_pm`：88项测试通过，结果 `OK`。
- `git diff --check`：通过。
- 测试输出中的 `OSError: 文件被占用` 为既有错误恢复测试主动模拟的日志，不影响结果。

## 范围

仅修改 `tokenDemo/autoTrade_pm.py`、`tokenDemo/test_autoTrade_pm.py` 和本fix-note；未修改AUTOA逻辑，未带入工作区其他改动，未执行commit或push。
