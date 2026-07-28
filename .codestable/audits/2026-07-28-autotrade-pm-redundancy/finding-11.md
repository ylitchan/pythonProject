---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 11
nature: performance
severity: P2
confidence: high
suggested_action: cs-refactor
summary: stock_zh_a_hist 对同一 res 重复构建 DataFrame
tags: [autotrade-pm, repeat-call]
---

# stock_zh_a_hist 对同一 res 重复构建 DataFrame

## 位置

`tokenDemo/autoTrade_pm.py:2980-2992`

## 证据

```python
hist_today = pd.DataFrame(res)
required_columns = ["m", "v", "p", "avg_p"]
if not set(required_columns).issubset(hist_today.columns):
    ...
hist_today = hist_today[required_columns].copy()
hist_today["v"] = pd.to_numeric(hist_today["v"], errors="coerce")
hist_today["p"] = pd.to_numeric(hist_today["p"], errors="coerce")
hist_today["tot_v"] = pd.to_numeric(
    pd.DataFrame(res).get("tot_v"), errors="coerce"
)
```

## 为什么是问题

同一条成功路径里，对同一份 `res` 先后调用了两次 `pd.DataFrame`：先在 2980 建成 `hist_today`，2987 再按 `required_columns=["m","v","p","avg_p"]` 做列子集，把可能存在的 `tot_v` 一并丢掉，到 2991 又不得不 `pd.DataFrame(res).get("tot_v")` 再物化一次才能取回该列。

这不是有意的防御性重读，而是子集顺序导致的多余物化。`hist_cache` 只缓存日 K，不覆盖新浪分时这段逻辑，因此每次走通该分支都会重复构造。属本地小表 CPU 冗余，非网络重复请求。

## 影响面

不修则每次成功拉取并解析分时数据时，都会对同一份 `res` 多做一次 DataFrame 构造与列访问，放大高频调用下的解析开销。修动点集中在 `tokenDemo/autoTrade_pm.py:2980-2992` 这一段；下游仍依赖 `hist_today["tot_v"]`（如 2996-2998 的 `total_volume` 取值与 `v` 求和兜底），只要保持 `tot_v` 列语义与 `dropna(subset=["p"])` 后的索引对齐不变，调用面行为可保持等价。

## 建议改法

- 主建议（安全等价）：在 `hist_today = pd.DataFrame(res)` 之后、按 `required_columns` 子集之前，先取出 `tot_v`（例如 `tot_v_series = hist_today.get("tot_v")`），子集后再 `hist_today["tot_v"] = pd.to_numeric(tot_v_series, errors="coerce")`，删除第二次 `pd.DataFrame(res)`。
- 备选：把 `tot_v` 纳入保留列再 `to_numeric`。注意这会改变「缺列时早退」的语义（当前 `required_columns` 不含 `tot_v`，缺 `tot_v` 不会触发 2982-2986 早退），不如主建议稳妥。
- 不要写完整实现；以子集前取列、去掉二次 `DataFrame(res)` 为改动要点即可。

## 对抗验证记录

视角一对照 `tokenDemo/autoTrade_pm.py:2980-2992` 实读与本地 pandas 等价实验：同一路径对同一 `res` 两次 `pd.DataFrame` 成立；子集前取 `tot_v` 再 `to_numeric`，在「有 tot_v / 无 tot_v 走 2997-2998 兜底 / dropna 后索引对齐」三种路径上与原写法结果一致，不改变返回值或空数据/异常行为。视角二逐字核对同一行段：证据与源码一致、行号无偏移，非已定案项、也非 ruff 机械基线复述；属真实重复 DataFrame 物化，发现成立，severity 按模板记 P2、置信度 high 无需修正。
