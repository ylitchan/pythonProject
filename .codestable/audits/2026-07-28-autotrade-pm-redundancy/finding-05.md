---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 05
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
summary: should_open 后 atr/hl2 兜底与二次止盈止损计算是死路径
tags: [autotrade-pm, dead-code]
---

# should_open 后 atr/hl2 兜底与二次止盈止损计算是死路径

## 位置

`tokenDemo/autoTrade_pm.py:2061-2069`

## 证据

```python
if atr_value is None or hl2 is None:
    # 兜底：确保后续止盈止损计算可用
    hl2 = (kline[-1][2] + kline[-1][3]) / 2
    atr_value = self.calculate_atr(kline)
zy, zs = self.calc_stop_profit_loss(
    hl2, is_long=is_long, atr=atr_value
)
if zy == 0 and zs == 0:
    return
```

## 为什么是问题

`should_open` 只在 `long_ok` / `short_ok` 分支内、且 `if not (zy_msg == 0 and zs_msg == 0)` 通过后才被置为 `True`；置位前已对同一 `kline` 计算过 `hl2`、`atr_value` 与 `calc_stop_profit_loss`。因此进入 `should_open` 时 `atr_value` / `hl2` 必非 `None`，2061 的 `None` 兜底永不触发。

随后用相同参数再算 `zy` / `zs`，结果必等于已通过非零校验的 `zy_msg` / `zs_msg`，故 2068 的 `zy == 0` 早退也永不成立。整段是外层已保证条件下的重复校验与死分支。

## 影响面

不修：代码里保留永远不可达的兜底与二次计算，增加阅读与改动成本；后续若有人误以为该兜底可防御 `calculate_atr` 失败或空数据，会掩盖真实失败路径。

修了会碰到的调用点：`tokenDemo/autoTrade_pm.py:2056-2069` 的 `if should_open` 开仓段；其上游置位点为 `2013`（多头）与 `2055`（空头），以及此前同段内的 `hl2` / `atr_value` / `zy_msg` / `zs_msg` 计算（约 `1987-1993`、`2029-2035`）。开仓入参 `open_bn_position` 使用的 `zy` / `zs`（约 `2074-2079`）改为复用 `zy_msg` / `zs_msg` 即可。

## 建议改法

在 `should_open` 分支直接复用前面的 `zy_msg` / `zs_msg`（或赋给 `zy` / `zs`），删除 `atr` / `hl2` 的 `None` 兜底、二次 `calc_stop_profit_loss` 以及 `zy == 0` 早退。开仓与消息展示共用同一对止盈止损值。

## 对抗验证记录

通读 `rzq_token` 开仓段（约 1965–2069）与 `calc_stop_profit_loss` / `calculate_atr` 实现后，控制流可静态穷举：`should_open` 仅在 2013、2055 两处置 `True`，且都嵌在 `long_ok` / `short_ok` 内、在 `hl2` / `atr_value` 赋值以及非零校验通过之后；`calculate_atr` 失败只返回 `0.0` 从不返回 `None`，二次计算对相同输入为纯函数，结果必等于已通过校验的 `zy_msg` / `zs_msg`。另一视角核对证据与源码一字不差，确认 2061 兜底与 2068 早退均不可达；该段非承重路径，发现成立，无法推翻。
