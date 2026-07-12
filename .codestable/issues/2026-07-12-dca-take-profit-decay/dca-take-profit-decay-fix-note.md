---
doc_type: issue-fix
issue: 2026-07-12-dca-take-profit-decay
status: fixed
severity: P1
summary: AUTOA 与 AUTOBN 的 DCA 止盈距离改为按 0.5 的 DCA 次数幂次收紧
tags: [autoa, autobn, dca, take-profit]
---

# DCA 止盈距离幂次衰减 Fix Note

## 问题与根因

AUTOA 与 AUTOBN 在 DCA 成功后使用 `ATR × 0.5 × DCA次数` 计算止盈价相对最新持仓均价的距离。该公式会让 DCA 次数越多时止盈距离越大，与逐次收紧止盈的策略口径相反。

正确口径为 `ATR × (0.5 ** DCA次数)`：第一次 DCA 距离为 `0.5 ATR`，第二次为 `0.25 ATR`，第三次为 `0.125 ATR`。

## 修复

- AUTOBN LONG：候选止盈价改为 `最新均价 + ATR × (0.5 ** DCA次数)`。
- AUTOBN SHORT：候选止盈价改为 `最新均价 - ATR × (0.5 ** DCA次数)`。
- AUTOA LONG：候选止盈价改为 `加权均价 + ATR × (0.5 ** DCA次数)`。
- 保留原有单向收紧限制：LONG 使用 `min(原止盈, 候选止盈)`，SHORT 使用 `max(原止盈, 候选止盈)`。
- 未修改 DCA 触发条件、下单参数、ATR 算法、均价算法或其他止盈止损逻辑。

## 验证

新增三项第二次 DCA 回归测试：

- AUTOBN LONG：均价 10、ATR 2、第二次 DCA 后候选止盈为 10.5。
- AUTOBN SHORT：均价 10、ATR 2、第二次 DCA 后候选止盈为 9.5。
- AUTOA LONG：加权均价 11、ATR 2、第二次 DCA 后候选止盈为 11.5。

验证命令及结果：

- 目标测试：26 项通过。
- `uv run python -m unittest tokenDemo.test_autoTrade_pm`：40 项通过。
- Python 编译检查：通过。
- `git diff --check`：通过。

所有测试均使用 mock，不访问真实账户、不真实下单。

## 影响范围

仅修改 `tokenDemo/autoTrade_pm.py` 中 AUTOA 与 AUTOBN 三处 DCA 成功后的候选止盈距离公式，以及对应回归测试。

## 顺手发现

无。
