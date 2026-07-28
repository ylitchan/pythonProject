---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 01
nature: maintainability
severity: P1
confidence: high
suggested_action: cs-refactor
summary: close_bn_position 三处完整平仓清理块重复未封装
tags: [autotrade-pm, dup-code]
---

# close_bn_position 三处完整平仓清理块重复未封装

## 位置

`tokenDemo/autoTrade_pm.py:893-897,965-969,999-1003`

## 证据

```python
self._handle_closed_position_observation(
    symbol, close_info, time.time()
)
if symbol in self.alert_all["POSITIONS"]:
    self.alert_all["POSITIONS"].pop(symbol)
```

以上模式在 893-897、965-969、999-1003 三处几乎完全一致；`_handle_closed_position_observation` 只抽了 OBSERVATIONS，POSITIONS pop 仍散落三处。

## 为什么是问题

全项目检索显示 `_handle_closed_position_observation` 仅在 `autoTrade_pm.py` 这三处被调用（无测试或其他模块另路引用）。每次完整平仓都是「observation 处理 + POSITIONS pop」同一套动作，但只抽了前半段；后半段还带着多余的 `if symbol in ...: pop`（可直接 `pop(symbol, None)`）。

任何清理语义变更都要改三处，是典型未封装重复：维护成本高，且同函数内多处拷贝更容易漏改。

## 影响面

不修则后续若调整平仓清理语义（例如 OBSERVATIONS 与 POSITIONS 的成对清理、pop 写法、额外本地状态），必须同步改 `tokenDemo/autoTrade_pm.py:893-897`、`965-969`、`999-1003` 三处，漏改会导致某条路径仓位残留或观察未清。

修了会碰到上述三个调用点，均在 `close_bn_position` 内：路径1（下单前 amount==0 早退）、路径2（下单后 remaining_amount==0）、路径3（异常后 amount==0）。测试侧只 mock/调用 `close_bn_position` 整体，不单独依赖散落写法。

## 建议改法

扩展或新增一个 `_clear_closed_position(symbol, close_info, ts)`，内部调用 `_handle_closed_position_observation`，再 `self.alert_all["POSITIONS"].pop(symbol, None)`。三个调用点改为单行调用该 helper。

要点：
- 用 `pop(symbol, None)` 替代 `if symbol in ...: pop`，语义等价且更简洁
- 调用点保留各自 return / fall-through 控制流，不把早退与 if-elif 余仓更新揉进 helper
- 不在本审计阶段写完整实现，交由 `cs-refactor` 落地

## 对抗验证记录

视角一：Read 核对三处清理块同形（893-897、965-969、999-1003 均为 observation + POSITIONS pop）；Grep 确认 helper 仅此三处调用；抽出后三路径语义与 `pop(key, None)` 等价性均成立，不能推翻「重复未封装」。

视角二：证据属实未编造，行号无偏移；`_handle_closed_position_observation` 只封装 OBSERVATIONS 侧，POSITIONS pop 仍散落；不撞已定案项，也非 ruff 机械复述。P1/high 定级合理，无需修正。
