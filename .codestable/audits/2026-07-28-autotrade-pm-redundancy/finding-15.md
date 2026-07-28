---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 15
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
summary: DataFrame 两分支赋值完全相同
tags: [autotrade-pm, redundant-guard]
---

# calculate_chebyshev_probability 的 DataFrame 两分支完全相同

## 位置

`tokenDemo/autoTrade_pm.py:2560-2566`

## 证据

```python
elif isinstance(data, pd.DataFrame):
    if data.shape[1] != 1:
        # 如果是多列 DataFrame，尝试取第一列，或者抛出异常
        # 这里假设用户传入的是单列数据
        series = data.iloc[:, 0]
    else:
        series = data.iloc[:, 0]
```

## 为什么是问题

`if data.shape[1] != 1` 与 `else` 两个分支都执行 `series = data.iloc[:, 0]`，列数判断对后续赋值零影响，是恒等死分支。注释写着「多列则尝试取第一列，或者抛出异常」，实际既未按列数分叉，也未 `raise`，注释与实现不一致。

空 DataFrame（0 列）两支都会在 `iloc[:, 0]` 上 `IndexError`；多列/单列也都只取第一列——没有任何执行路径会因删掉该 if/else 而改变行为。属于冗余判断，不是承重防御。

## 影响面

不修则 DataFrame 路径继续保留无意义分支与误导性注释，可读性差，后续维护者可能误以为多列会抛异常。

当前实际调用方基本不走 DataFrame 分支：

- `tokenDemo/autoTrade_pm.py:3292`（`on_observations`）：`volume_sample` 为 `hist_volume` 切片（ndarray），走 else→`pd.Series`
- `tokenDemo/autoTrade_pm.py:1212`、`1910`：传入 list/序列形态数据
- `tokenDemo/test_backtest_autoa_parity.py:56`：传入 `list(sample)`

直接删 if/else、保留 `series = data.iloc[:, 0` 对现有调用零行为变化；若改为多列 `raise` 才会改变语义，但当前无调用方传多列 DF。

## 建议改法

- 删掉 if/else，直接 `series = data.iloc[:, 0]`（零行为变化，与现状等价）
- 若真要限制单列：多列时 `raise ValueError(...)`，与注释意图一致；但需确认无调用方依赖「多列静默取第一列」

不要在 cs-audit 阶段写完整实现。

## 对抗验证记录

视角一核对 `autoTrade_pm.py:2560-2566` 原文：两支均为 `series = data.iloc[:, 0`，`shape[1]` 对控制流无影响，行号无偏移。视角二确认调用点（`on_observations` 的 ndarray 切片、`test_backtest_autoa_parity` 的 list）均不走 DataFrame 路径，注释写「或抛异常」却未 raise，构成真实冗余判断而非纯风格问题；P2/high 定级合理，发现成立。
