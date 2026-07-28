---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 04
nature: performance
severity: P2
confidence: high
suggested_action: cs-refactor
summary: 开仓信号路径 calc_stop_profit_loss 同参计算两次
tags: [autotrade-pm, repeat-call]
---

# 开仓信号路径 calc_stop_profit_loss 同参计算两次

## 位置

`tokenDemo/autoTrade_pm.py:1989-1993`（多头）/ `:2031-2035`（空头）与 `:2065-2067`

## 证据

多头分支先算一次：

```python
hl2 = (kline[-1][2] + kline[-1][3]) / 2
atr_value = self.calculate_atr(kline)
zy_msg, zs_msg = self.calc_stop_profit_loss(
    hl2,
    is_long=True,
    atr=atr_value,
)
```

空头分支 `:2029-2035` 除 `is_long=False` 外完全同形。随后 `if should_open:` 段又算一次：

```python
is_long = open_info.side.value == OrderSide.BUY.value
if atr_value is None or hl2 is None:
    # 兜底：确保后续止盈止损计算可用
    hl2 = (kline[-1][2] + kline[-1][3]) / 2
    atr_value = self.calculate_atr(kline)
zy, zs = self.calc_stop_profit_loss(
    hl2, is_long=is_long, atr=atr_value
)
```

`calc_stop_profit_loss` 是纯函数（`:1410-1420`，只读 `price` / `is_long` / `atr` 和类常量 `SUPERTREND_FACTOR`，无副作用、无 IO）：

```python
def calc_stop_profit_loss(self, price, is_long=True, atr=0):
    if atr <= 0:
        return (0, 0)
    atr_distance = atr * self.SUPERTREND_FACTOR
    if is_long:
        return (price + atr_distance, price - atr_distance)
    else:
        return (price - atr_distance, price + atr_distance)
```

## 为什么是问题

三个入参在两次调用之间都没变过：

- `hl2` / `atr_value` — 第一次调用前赋值（`:1987-1988` 或 `:2029-2030`），到 `:2065` 之间只有 `:2061-2064` 那段 `None` 兜底可能重写，而该段不可达（详见 [finding-05](finding-05.md)）。
- `is_long` — `:2060` 由 `open_info.side` 推出，而 `open_info.side` 正是在两个分支里跟 `should_open = True` 一起置的（`:2012-2013` 置 BUY、`:2054-2055` 置 SELL），所以 `is_long` 必然等于第一次调用时传的那个 `is_long`。

于是 `:2065` 的 `zy` / `zs` 恒等于 `:1989`（或 `:2031`）已算出的 `zy_msg` / `zs_msg`——同参调同一个纯函数，第二次纯属重算。

这不是热点性能问题（纯算术，开销可忽略），真正的代价是**同一对止盈止损值有两个来源**：推送给用户的消息用 `zy_msg` / `zs_msg`（`:2006`、`:2010`），实际下单用 `zy` / `zs`（`:2074` 之后）。今天二者恒等，但只要有人改动其中一条计算路径（换 `hl2` 口径、加 DCA 系数、改 `SUPERTREND_FACTOR` 的取用方式），消息和实际下单就会静默不一致——用户看到的止盈止损跟挂上去的不是同一个值，且没有任何断言会拦住。

## 影响面

不修：`rzq_token` 开仓段的止盈止损存在两条并行计算路径，后续任何单侧改动都可能造成"通知与实际挂单不一致"，且这类偏差在日志里表现为消息数字对但单子不对，排查成本高。

修了会碰到：`tokenDemo/autoTrade_pm.py:1985-2013`（多头信号段）、`:2027-2055`（空头信号段）、`:2056-2069`（`should_open` 段）以及 `:2074` 起 `open_bn_position` 的 `zy` / `zs` 入参。

与 [finding-05](finding-05.md) 是**同一段代码的两个侧面**（本条看重复调用，05 看死分支），应当一次改完，不要拆成两次改动。

## 建议改法

`should_open` 段直接复用前面已算好的 `zy_msg` / `zs_msg`，删掉 `:2065-2067` 的二次调用；连带 `:2061-2064` 的 `None` 兜底和 `:2068-2069` 的 `zy == 0` 早退按 finding-05 一并处理。改完后开仓与消息展示共用同一对值，来源唯一。

## 对抗验证记录

本条的自动验证 agent 在网关 524 中断，证据由我手工复核：

- 读 `:1410-1420` 确认 `calc_stop_profit_loss` 是纯函数，同参必同结果。
- 读 `:1985-2069` 全段确认 `hl2` / `atr_value` 在两次调用之间的唯一写入点是不可达的 `:2061-2064`，`is_long` 与 `open_info.side` 的置位点同源。
- 因此"第二次调用结果恒等于第一次"成立，重复调用属实，行号无偏移。
- 定级取 P2 而非 P1：单次重算的运行时开销可忽略，风险在于未来改动时的静默分叉，不是当下的错误行为。
