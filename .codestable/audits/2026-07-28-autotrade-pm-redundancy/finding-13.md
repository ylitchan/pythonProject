---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 13
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
summary: calculate_atr 中 tr_list 长度守卫前置后恒假
tags: [autotrade-pm, redundant-guard]
---

# calculate_atr 中 len(tr_list) < period 在前置守卫后恒假

## 位置

`tokenDemo/autoTrade_pm.py:1382-1396`

## 证据

```python
if not kline_data or len(kline_data) < period + 1:
    return 0.0

tr_list = []
for i in range(1, len(kline_data)):
    high = kline_data[i][2]
    low = kline_data[i][3]
    prev_close = kline_data[i - 1][4]

    # TR = Max(H-L, |H-PC|, |L-PC|)
    tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
    tr_list.append(tr)

if len(tr_list) < period:
    return 0.0
```

## 为什么是问题

前置条件已要求 `len(kline_data) >= period + 1`，而 `tr_list` 由 `range(1, len(kline_data))` 生成，长度恒为 `len(kline_data) - 1`，因此通过第一道守卫后必然 `len(tr_list) >= period`。第二段 `if len(tr_list) < period` 永远走不到，是被外层已保证的重复校验，属于死代码守卫。

同文件类方法版 `calculate_atr`（约 2487 行）使用的是 `if not tr_list` 而非 `len < period`，侧面印证实例方法这段是复制遗留的冗余判断。

## 影响面

不修则留下误导性的“安全网”：阅读者会以为第二段守卫在兜底短 `tr_list`，实际永不触发；对 `period <= 0` 的异常输入也救不了（`tr_len < 0` 恒假，仍可能落到 `sum(...)/0` 的 ZeroDivisionError）。删掉后正常路径、空数据、短 K 线、异常输入、首次无缓存等路径行为均不变。

真实调用点（`tokenDemo/autoTrade_pm.py:1825`、`1988`、`2030`、`2064` 及同类调用）均不传 `period`，默认 `ATR_PERIOD=10 > 0`；无测试直接覆盖该守卫。修只需触及该函数内 1395-1396 两行，不改调用约定。

## 建议改法

- 直接删除 1395-1396 的 `len(tr_list) < period` 守卫即可。
- 若仍想防御异常输入，只保留前置的 `period + 1` 检查（并可按需对 `period <= 0` 单独早退），不要再叠一层恒真的 `tr_list` 长度判断。
- 不要写完整实现；此条仅发现、不定修，落地走 `cs-refactor`。

## 对抗验证记录

独立视角一：Read 源码确认 1382-1396 前置 `len(kline_data) < period + 1` 通过后，`tr_list` 长度恒为 `len(kline_data)-1`，故第二道守卫恒假。独立视角二：对 `period∈[-5,29]`、`n∈[0,39]` 穷举仿真 `second_return` 触发次数为 0，且删保留两段行为完全一致；全项目调用点与同文件另一版实现交叉印证。结论：发现成立，不可推翻；定级 maintainability/P2、置信度 high 合理。
