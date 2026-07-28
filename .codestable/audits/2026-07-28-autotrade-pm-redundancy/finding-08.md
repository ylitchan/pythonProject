---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 08
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
summary: 五枚类常量只定义从未被引用，其中三枚与 BD 入池的硬编码切片数值重合
tags: [autotrade-pm, dead-code, magic-number]
---

# 五枚类常量只定义从未被引用，其中三枚与 BD 入池的硬编码切片数值重合

## 位置

`tokenDemo/autoTrade_pm.py:308`、`:314`、`:327`、`:343`、`:344`

## 证据

五枚常量在 `autoTrade_pm.py` 和 `test_autoTrade_pm.py` 里各只出现一次——就是定义那一行，零引用：

```python
MIN_KLINE_FOR_ANALYSIS = 4  # 分析所需最小K线数量                      # :308
LONG_SHORT_RATIO_SHORT_LIMIT = 7 / 3  # SHORT额外放行阈值（多空比）      # :314
OI_LOOKBACK_PERIOD = 10  # 持仓量检查回溯周期                           # :327
BD_OI_PEAK_LOOKBACK = 10  # 入池取近N日1d OI最大值参与切比雪夫           # :343
BD_VOLUME_PEAK_MIN_AGE = 3  # 量峰距今最少天数（避开资金成本位，<该值不入池）  # :344
```

对照 `_is_bd_observation`（`:1884-1901`）——这三枚常量描述的正是这段逻辑，但段内全是硬编码：

```python
if len(kline_close) < 30 or len(kline_volume) < 30:   # :1884  ← 不是 MIN_KLINE_FOR_ANALYSIS(4)
    return False
...
old_volume = kline_volume[-10:-3]                      # :1894  ← 10 / 3 硬编码
recent_volume = kline_volume[-3:]                      # :1895
...
oi_baseline = oi_window[:-10]                          # :1899  ← 10 硬编码
oi_old = oi_window[-10:-3]                             # :1900
oi_recent = oi_window[-3:]                             # :1901
```

同一个"回溯 10 根"的概念在本文件里两种写法并存：`:2144` 用 `kline_volume[-self.VOLUME_LOOKBACK_PERIOD :]`（常量），`:1894` 用 `kline_volume[-10:-3]`（字面量）。

## 为什么是问题

这不是"多几行无害的定义"，是**假可配**：

1. `BD_OI_PEAK_LOOKBACK` / `BD_VOLUME_PEAK_MIN_AGE` 带着解释清楚的中文注释，摆在 `==== BD做空入池/扣扳机常量 ====` 分节下，紧邻真正在用的 `BD_OI_DRAWDOWN_RATIO`（`:345`，`_close_triggered_position` 侧实际读取）。谁要调 BD 入池的回溯窗口，最自然的动作就是改这两个数——改完跑一轮发现行为一模一样，因为真正生效的是 `:1894-1901` 的字面量。这类"改了没反应"的坑排查成本远高于常量本身的价值。
2. `MIN_KLINE_FOR_ANALYSIS = 4` 更糟：它的**值与实际守卫矛盾**。真实门槛是 `:1884` 的 `< 30`，常量却写 4。按常量理解代码会得出"4 根 K 线就能分析"的错误结论。
3. `OI_LOOKBACK_PERIOD = 10` 与 `:1899-1900` 的 `10` 同义，属同一组失联常量。
4. `LONG_SHORT_RATIO_SHORT_LIMIT = 7 / 3` 没有对应的硬编码残留——SHORT 侧现在走 `check_side` 的切比雪夫路径，这枚是旧"多空比阈值放行"口径的遗留，纯孤儿。

## 影响面

不修：常量区看起来像一份可调参数表，其中五项实际不接线，两项还会误导 BD 入池调参，一项的值与真实守卫矛盾。

修了会碰到：`tokenDemo/autoTrade_pm.py:308`、`:314`、`:327`、`:343-344`（常量定义），以及若选择"接线"则还会碰到 `:1884`、`:1894-1895`、`:1899-1901`（`_is_bd_observation` 内的切片）。`_is_bd_observation` 有测试覆盖（BD 入池/刷新用例），接线改动属纯等价替换，回归点明确。

## 建议改法

两条路二选一，**不要都不做**：

- **接线**（推荐用于 BD 三枚）：`:1894-1901` 的 `10` / `3` 换成 `self.BD_OI_PEAK_LOOKBACK` / `self.BD_VOLUME_PEAK_MIN_AGE`，`OI_LOOKBACK_PERIOD` 与 `BD_OI_PEAK_LOOKBACK` 择一保留（同义重复），顺手让 `:1894` 与 `:2144` 的写法统一。
- **删除**（推荐用于 `MIN_KLINE_FOR_ANALYSIS` / `LONG_SHORT_RATIO_SHORT_LIMIT`）：前者的值与 `:1884` 的真实门槛不一致，接线会改变行为，不属于本审计范围内的等价重构，直接删更诚实；后者是旧口径孤儿，直接删。

## 对抗验证记录

本条的自动验证 agent 在网关 524 中断，证据由我手工复核：

- 逐枚 grep `autoTrade_pm.py` + `test_autoTrade_pm.py`，五枚常量的匹配结果均只有定义行本身；对照组 `LONG_SHORT_RATIO_LIMIT`（`:311`）命中 `:1279`、`:1295`、测试 `:1480`，`VOLUME_LOOKBACK_PERIOD`（`:328`）命中 `:2144`，证明 grep 口径能正确抓到真实引用，不是搜索失效。
- 读 `:1884-1914` 确认 `_is_bd_observation` 内的 `30` / `10` / `3` 全为字面量，与三枚常量语义对应但无引用关系。
- `MIN_KLINE_FOR_ANALYSIS = 4` 与 `:1884` 的 `< 30` 数值不一致，故这枚不能当"待接线"处理——已在建议改法里分开对待。
- 定级取 P2：不影响当前任何行为，但"假可配"对后续调参有实质误导，高于纯粹的未使用变量。
