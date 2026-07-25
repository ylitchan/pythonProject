---
doc_type: audit-finding
audit: 2026-07-25-bd-price-condition-ab
finding: 01
nature: bug
severity: P1
confidence: medium
suggested_action: cs-feat
---

# high-to-high 增加逼空尾部

## 证据

生产候选条件位于 `tokenDemo/autoTrade_pm.py` 的 BD 观察价格腿；现行校准逻辑见 `tokenDemo/calibrate_short_oi_drawdown.py:138-150`。在同一批 529 个 USDT 永续、其余条件固定的快照中：

- close-to-close：8 次触发；3 日 n=5，均值 `-5.526%`，中位数 `-10.432%`，下跌率 `80%`，最大上涨 `+13.774%`。
- high-to-high：7 次触发；3 日 n=6，均值 `+10.525%`，中位数 `+2.353%`，下跌率 `50%`，最大上涨 `+60.918%`。
- B-only：3 次；3 日均值 `+21.875%`，最大上涨 `+60.918%`。

## 为什么构成问题

日内 high 只证明价格曾触及历史高点，不证明市场在高位获得收盘接受；在 OI 回撤发生后，它仍可能包含强势回踩或空头回补场景。直接替换会放宽到一组当前样本表现更差、逼空尾部更大的信号。

## 建议

本轮不改生产代码。若继续研究，先取得更长 OI 历史，并测试“high 创新高 + 收盘位置/锚日回落”等组合，按需求变更走 `cs-feat`。
