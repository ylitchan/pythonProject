---
doc_type: issue-fix
issue: 2026-07-12-dca-take-profit-dynamic-recalc
status: fixed
severity: P1
summary: AUTOA 与 AUTOBN 的 DCA 候选止盈在后续每分钟动态止盈中按当前 ATR 重算
tags: [autoa, autobn, dca, take-profit]
---

# DCA 候选止盈动态重算 Fix Note

## 问题与根因

AUTOA 与 AUTOBN 在 DCA 成功当轮会按 `entry_price ± ATR × (0.5 ** DCA次数)` 收紧止盈，但后续每分钟的普通动态止盈只比较衰减值与 Supertrend 轨道。ATR 变化后，DCA 候选止盈不会重新计算，也不再参与最终止盈价比较。

## 修复

- AUTOBN LONG：已有 DCA 时，每分钟用当前 ATR 计算 `dca_tp`，最终取 `max(min(decayed_tp, current_upper, dca_tp), entry_price)`。
- AUTOBN SHORT：已有 DCA 时，每分钟用当前 ATR 计算 `dca_tp`，最终取 `min(max(decayed_tp, current_lower, dca_tp), entry_price)`。
- AUTOA LONG：已有 DCA 时，每分钟用当前 ATR 计算 `dca_tp`，最终取 `max(min(decayed_tp, current_upper, dca_tp), entry_price)`。
- 仅当 `dca_count > 0` 时引入 DCA 候选；无 DCA 的持仓继续使用原动态止盈公式。
- 未修改 DCA 触发条件、下单参数、ATR 算法、Supertrend 算法或止损逻辑。

## 验证

新增回归测试覆盖：

- AUTOA 已有 DCA 时，后续分钟使用当前 ATR 重算 LONG 止盈。
- AUTOBN 第二次 DCA 后，后续分钟分别重算 LONG 与 SHORT 止盈。
- AUTOBN 无 DCA 时，LONG 与 SHORT 保持原动态止盈结果。

验证命令及结果：

- 新增目标测试：5 项通过。
- `uv run python -m unittest tokenDemo.test_autoTrade_pm`：45 项通过。
- `uv run python -m py_compile tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py`：通过。
- `git diff --check`：通过。

测试均使用 mock，不访问真实账户、不真实下单。完整测试中的“文件被占用”异常为既有 Excel 失败保留队列测试的预期 mock 输出，测试结果为 OK。

## 影响范围

仅修改 `tokenDemo/autoTrade_pm.py` 中 AUTOA LONG、AUTOBN LONG、AUTOBN SHORT 的普通动态止盈分支，以及 `tokenDemo/test_autoTrade_pm.py` 中对应回归测试。

## 顺手发现

无。
