---
doc_type: issue-fix
issue: 2026-07-26-bd-short-lsr-stop
status: fixed
severity: P1
summary: 多空比止损限定为多头专属，BD 空头不再因常态多空比被立即平仓
tags: [autobn, bd, short, stop-loss, long-short-ratio]
---

# BD 空头多空比止损 Fix Note

## 问题与目标

`_close_triggered_position` 的多空比止损判定没有方向限制，空头分支是
`latest_lsr <= LONG_SHORT_RATIO_STOP_LOSS_THRESHOLD`，阈值为 `6 / 4 = 1.5`。
而多空人数比常态在 1 附近，该条件对空头几乎恒真，导致 BD 开仓后基本在下一轮
就被"多空比止损"全量平掉，做空逻辑无法走完。

期望行为：多空比止损只对多头（BZ 等 LONG 持仓）生效；BD 空头的退出只由初始止损、
止盈、追踪/移动止损决定，不受多空比影响。

范围经用户确认：只删空头侧，多头风控保持不变。

## 修复

- `tokenDemo/autoTrade_pm.py:1586-1590`：多空比止损进入条件增加 `is_long`，
  删除 `not is_long and latest_lsr <= 阈值` 的空头分支，判定简化为
  `latest_lsr >= LONG_SHORT_RATIO_STOP_LOSS_THRESHOLD`。

OI 止损原本就被 `is_long` 挡住、且空头开仓时 `stop_guard_threshold` 恒为 `0.0`，
本次不需要改动。

## 验证

新增 3 项测试（`AutoBNCharacterizationTest`）：

- `test_short_position_ignores_low_long_short_ratio` — 空头 + 多空比 1.0，
  不平仓且不请求 5m OI。
- `test_short_position_ignores_high_long_short_ratio` — 空头 + 多空比 9.0，
  同样不平仓（锁死空头完全不受多空比影响，而非只调阈值方向）。
- `test_long_position_still_stops_on_high_long_short_ratio` — 多头 + 多空比 9.0
  仍触发平仓，`close_reason` 为"多空比止损"，确认多头风控未被误删。

反向验证：临时把实现回退为旧逻辑后
`test_short_position_ignores_low_long_short_ratio` 报红，确认新用例真正锁住行为，
随后恢复修复版本。

测试命令：

```text
uv run python -m unittest tokenDemo.test_autoTrade_pm
```

结果：69 项测试全部通过（原 66 + 新增 3）。日志中"文件被占用"堆栈是既有的
平仓记录错误路径测试，非本次引入。

静态检查：

```text
uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py
```

结果：All checks passed!

## 影响范围

只改 AUTOBN 已有持仓的多空比止损判定分支。开仓条件、OI 止损、初始止损止盈、
追踪/移动止损、平仓比例、AUTOA 均未修改。`get_long_short_ratio` 的调用时机不变
（空头未触发价格止损止盈时仍会请求一次，用于同轮判定），只是结果不再作用于空头。

## 遗留

- `tokenDemo/autoTrade.py` 与 `tokenDemo/autoTrade_papi.py` 是其他实现，未在本次
  范围内核查是否有同样的空头多空比止损；用户此前已明确只关注 `autoTrade_pm.py`。
- 未提交或推送；版本控制动作等待用户明确授权。
