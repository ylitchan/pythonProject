---
doc_type: issue-fix
issue: 2026-07-25-open-failure-local-position
status: fixed
severity: P0
summary: 交易所开仓失败时不再创建本地虚假持仓
tags: [autobn, order, position-state]
---

# open-failure-local-position fix note

## 问题与根因

`tokenDemo/autoTrade_pm.py` 的首次开仓流程忽略 `open_bn_position()` 返回值；该方法失败时返回假值，但调用方仍构造并写入 `Position`，造成交易所无仓、本地有仓。

## 修复

保存开仓调用结果；结果为假时立即退出，只有成功结果才继续创建并写入本地 `POSITIONS`。不改变DCA、止盈止损或策略判断。

## 验证

- 新增失败路径刻画：`open_bn_position()` 返回 `None` 时不写入 `POSITIONS`，原观察保持不变。
- `uv run python -m unittest tokenDemo.test_autoTrade_pm`：54项全部通过。
- 测试中的“文件被占用”堆栈是既有模拟失败路径，最终套件状态为 `OK`。

## 影响范围

- `tokenDemo/autoTrade_pm.py`
- `tokenDemo/test_autoTrade_pm.py`
