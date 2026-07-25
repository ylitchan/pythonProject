---
doc_type: audit-finding
audit: 2026-07-25-bd-price-condition-ab
finding: 02
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
---

# 30 日 OI 窗口造成前瞻样本右截断

## 证据

Binance 日级 OI 接口当前仅提供约 30 日数据；触发逻辑还需锚点后的 1～5 日，因此越靠近数据快照末端，越缺少完整前瞻收益。此次 A 的前瞻样本由 1 日 n=6 降至 5 日 n=4，B 由 n=6 降至 n=3。

现有实现的相关口径见：

- `tokenDemo/calibrate_short_oi_drawdown.py:188-205`：OI 入池窗口。
- `tokenDemo/calibrate_short_oi_drawdown.py:219-238`：锚点后触发与前瞻收益。

## 为什么构成问题

5 日均值由极少事件决定：A 的 5 日均值被单笔 `+37.243%` 拉至正值；B 的 5 日仅剩 3 个样本。忽略实际 n 会把数据留存限制误判为策略差异。

## 建议

报告每个周期的实际 n、中位数和尾部，不以 5 日均值单独决策。后续可用定时落盘构建本地长历史，但这属于校准工具能力扩展，应另走 `cs-refactor` 或相应功能流程。
