---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 16
nature: maintainability
severity: P2
confidence: medium
suggested_action: cs-refactor
summary: ATR 初始化路径上 hl2 计算两次
tags: [autotrade-pm, repeat-call]
---

# ATR 初始化路径上 hl2 计算两次

## 位置

`tokenDemo/autoTrade_pm.py:1832,1849`

## 证据

```python
if (
            close_info.take_profit == 0 or close_info.stop_loss == 0
        ) and atr_value > 0:
            is_long = close_info.position_side.value == PositionSide.LONG.value
            # 使用hl2中间价计算止盈止损，与supertrend保持一致
            hl2 = (kline[-1][2] + kline[-1][3]) / 2  # (high + low) / 2
            tp, sl = self.calc_stop_profit_loss(
                hl2, is_long=is_long, atr=atr_value
            )
            close_info.take_profit = tp
            close_info.stop_loss = sl
            ...

        if await self._close_triggered_position(...):
            return open_info

        # 计算当前supertrend上下轨，用于止盈边界限制
        hl2 = (kline[-1][2] + kline[-1][3]) / 2  # (high + low) / 2
        current_upper = hl2 + atr_value * self.SUPERTREND_FACTOR
        current_lower = hl2 - atr_value * self.SUPERTREND_FACTOR
```

## 为什么是问题

同一 `_manage_position` 调用、同一根 `kline[-1]` 上，`(high+low)/2` 写了两遍。第一条仅在 `take_profit==0 or stop_loss==0` 且 `atr>0` 时执行；若该分支命中且未在 `_close_triggered_position` 提前 return，则会再算一次完全相同的 hl2 给上下轨。两次之间 kline 不被改写：`_close_triggered_position` 只读 `close_info`/`current_price`，并可能 await 平仓/LSR/OI，不碰 kline。

两处不是因语义不同而必须分开。init 用 hl2 做 `calc_stop_profit_loss` 基价，后续用同一 hl2 做 supertrend 上下轨，本就要求一致；分开写只是控制流先后（init 必须在 close 检查前，因为 close 会读刚写入的 tp/sl；轨只需在未平仓后算）。非初始化路径只算一次，故标 medium；命中初始化且继续管理时必然重复。

## 影响面

不修：仅在 ATR 初始化命中且 `_close_triggered_position` 未提前 return 时多一次本地浮点运算；可观察行为（tp/sl、上下轨）不受影响，但重复字面计算增加阅读负担，后续若改 hl2 定义易漏改一处。

相关调用与路径：

- `_manage_position`：`tokenDemo/autoTrade_pm.py:1821-1872`（1832 初始化、1849 上下轨）
- `_close_triggered_position`：`tokenDemo/autoTrade_pm.py:1527-1581`（两次 hl2 之间，不改 kline）
- 调用方 `rzq_token`：约 `1946-1954`（`len(kline) < KLINE_LIMIT` 时直接 return，进入管理时 `kline[-1]` 可用）
- 测试：`test_autoTrade_pm` 中 `_manage_position` 用例；`calculate_atr`/`calc_stop_profit_loss` 常被 mock，不依赖「算两次」语义

`calculate_atr` 内部约 1405 行另有一次同式 hl2 仅用于 atr_cap 且不返回，不消除 `_manage_position` 字面两处。

## 建议改法

在 `_close_triggered_position` 之前或之后只算一次 hl2，初始化与 upper/lower 共用；若提前 return 可选择懒计算 upper/lower。

路径行为保持一致的要点：

- init 命中且 atr>0 且未在 close 处 return：现算 2 次 → 改后 1 次，值相同，tp/sl 与上下轨不变
- init 命中且 atr>0 且 close 触发 return：现只在 init 算 1 次 → 改后仍 1 次，upper/lower 本就不跑
- 非 init 且继续管理：现只在 1849 算 1 次 → 改后 1 次
- 非 init 且提前 return：现 0 次 hl2；若无条件提前到 close 之前会多一次未使用本地浮点运算，无任何可观察副作用（不写字段、不打 API）；按「懒算 upper/lower」写法行为仍一致
- atr_value==0：init 跳过；若未平仓仍用 1849 的 hl2 算轨——与合并后相同

合并成一个局部变量不会破坏 init 必须在 close 检查前、轨在未平仓后算的顺序。

## 对抗验证记录

不能推翻。独立核对 `autoTrade_pm.py:1821-1872` 与 `_close_triggered_position:1527-1581`，并核对调用点 `rzq_token` 约 1946-1954 与 `test_autoTrade_pm` 中 `_manage_position` 用例：1832 与 1849 确为同一根 bar 的 `(kline[-1][2]+kline[-1][3])/2`，两次之间 kline 未改写；空 kline 路径不成立。属纯本地下标算术，非 API/DataFrame 缓存可兜住；行号无偏移。medium/P2 定级合适。
