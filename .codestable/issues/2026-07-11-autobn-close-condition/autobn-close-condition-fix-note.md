---
doc_type: issue-fix
issue: 2026-07-11-autobn-close-condition
status: fixed
severity: P1
summary: AUTOBN 价格止损统一由当前价触发，并以多空比大于 1 作为 LONG OI 止损前置条件
tags: [autobn, close-condition, risk-control]
---

# AUTOBN 平仓条件调整 Fix Note

## 问题与目标

AUTOBN 的部分价格止损需要上一根收盘价确认，不能由当前价直接触发；LONG 的 OI 止损以前以持仓浮盈为前置，不符合当前策略要求。

期望行为：所有价格止损统一使用当前价；LONG 在最新多空比大于 1、OI 阈值有效且最新 5m OI 不高于阈值时执行 OI 止损。

## 修复

- `tokenDemo/autoTrade_pm.py`：价格止损参考价统一为 `current_price`。
- `tokenDemo/autoTrade_pm.py`：先取得一次最新多空比；仅当 LONG 且多空比大于 1 时请求 5m OI。
- 同轮取得的多空比继续用于多空比止损判断，不重复请求。
- 删除不再使用的止损原因参考价辅助函数。

## 验证

- LONG 当前价跌破止损价时，即使上一根收盘价未跌破，也执行全部平仓。
- SHORT 当前价突破止损价时，即使上一根收盘价未突破，也执行全部平仓。
- LONG 即使浮亏，只要多空比大于 1 且 OI 达到阈值，仍执行 OI 止损。
- 多空比等于 1 时不请求 OI。
- OI 与多空比止损共用同轮的一次多空比请求。

测试命令：

```text
uv run python -m unittest tokenDemo.test_autoTrade_pm.AutoBNCharacterizationTest
```

结果：13 项测试全部通过。

## 影响范围

仅调整 AUTOBN 已有持仓的平仓判定。AUTOA、开仓条件、平仓比例及下单接口未修改。

## 遗留

- AUTOBN 调度分钟被跳过时，非持仓分片不会在当前窗口补跑；不属于本次修复范围。
