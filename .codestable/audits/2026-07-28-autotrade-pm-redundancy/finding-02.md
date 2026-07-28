---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 02
nature: maintainability
severity: P1
confidence: high
suggested_action: cs-refactor
summary: DCA开仓失败回滚条件恒真属多余校验
tags: [autotrade-pm, redundant-guard]
---

# DCA 开仓失败后的 strategy 回滚条件恒真，属多余校验

## 位置

`tokenDemo/autoTrade_pm.py:1616-1621,1735-1740`

## 证据

```python
# long 侧（short 侧 1706/1735-1740 结构相同）
close_info.strategy.append(PositionSide.DCA)  # 1587
if await self.open_bn_position(
    symbol,
    OrderSide.BUY.value,
    PositionSide.LONG.value,
    close_info.take_profit,
    close_info.stop_loss,
    close_info,
):
    ...
else:
    if (
        close_info.strategy
        and close_info.strategy[-1] == PositionSide.DCA
    ):
        close_info.strategy.pop()
```

`open_bn_position`（723-848）对传入的 `open_info`/`close_info` 只读 `strategy` 做文案，不改列表：

```python
strategy_tag = format_strategy_tags(open_info.strategy)  # 841，只读
# format_strategy_tags(131-143) 本身也只读（strategies or [] 遍历），从不 pop/clear/覆盖
# 所有失败 return None 与 except 路径均不碰 strategy
```

## 为什么是问题

进入 `else` 前一行必然刚执行 `close_info.strategy.append(PositionSide.DCA)`（long:1587 / short:1706）。`Position.strategy` 类型为必填 `List[PositionSide]`，append 后列表必非空，且末元素必为刚写入的 `DCA`。

同时，`open_bn_position`（723-848）仅在成功路径 841 通过 `format_strategy_tags` 只读 strategy；失败与异常一律 `return None`，从不 pop/clear/覆盖该列表。同 symbol 任务内 `close_info` 是局部 `model_validate` 出的独立对象，await 间隙无其他协程改这份列表。因此 `close_info.strategy and close_info.strategy[-1] == PositionSide.DCA` 在该路径上恒真，外层 if 守卫从不挡掉 pop，也从不因短路避免 IndexError（空列表路径不可达）。long/short 两处相同，属多余校验。

## 影响面

不修：行为本身正确（失败仍会 pop），但守卫文风暗示「可能不是 DCA / 可能为空」的假分支，增加阅读成本与后续误改空间；测试 `test_failed_long/short_dca_removes_appended_strategy...` 只断言失败后 strategy 回滚为 `[BZ]`，pop 必要，包在外的 if 从不被证伪。

修了会碰到：
- `tokenDemo/autoTrade_pm.py:1616-1621`（`_manage_long_position` else 回滚）
- `tokenDemo/autoTrade_pm.py:1735-1740`（`_manage_short_position` else 回滚）
- 相关失败回滚测试（断言 pop 结果，不依赖 if 为假）

全文件仅上述两处该模式，无其它调用点依赖该 if 为假。

## 建议改法

else 分支改为无条件 `close_info.strategy.pop()`；若想保留防御意图，可改 `assert close_info.strategy and close_info.strategy[-1] == PositionSide.DCA` 或注释说明「刚 append，失败必回滚」，不要留恒真 if。不要写完整实现——此处只定方向。

## 对抗验证记录

视角一按执行路径与调用图核：append 后必非空且末为 DCA；`open_bn_position`/`format_strategy_tags` 只读；并发与 POSITIONS 写路径不碰本 close_info.strategy；结论条件恒真。视角二复核行号与 long/short 结构一致，并区分本发现非 ruff PLR5501（后者只建议 elif，本条额外证明可无条件 pop）。按建议改成无条件 pop 后，当前所有可达路径行为不变，该 if 在现状下确属恒真冗余。
