---
doc_type: feature-ff-note
feature: extend-reopen-cooldown
date: 2026-07-26
requirement: shared-observation-reopen-cooldown
tags: [autobn, bz, observation, cooldown]
---

## 做了什么
将AUTOBN BZ确认完整平仓后的重开冷却从1小时恢复为24小时，冷却仍从交易所确认清仓时开始计算。

## 改了哪些
- `tokenDemo/autoTrade_pm.py:AUTOBN.REOPEN_COOLDOWN_SECONDS` — 将重开冷却调整为24小时。
- `tokenDemo/test_autoTrade_pm.py` — 同步三类确认归零及自然过期场景的冷却时长断言。
- `.codestable/requirements/shared-observation-reopen-cooldown.md` — 更新能力边界和变更日志。

## 怎么验证的
`uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py`通过；`uv run python -m unittest tokenDemo.test_autoTrade_pm`共88项测试通过；目标文件`git diff --check`通过。
