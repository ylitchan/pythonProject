---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 09
nature: performance
severity: P2
confidence: high
suggested_action: cs-refactor
summary: 切比雪夫返回 dict 多数字段从未被消费
tags: [autotrade-pm, dead-code]
---

# 切比雪夫结果里 message/min_probability_in_range 等字段从未被消费

## 位置

`tokenDemo/autoTrade_pm.py:1456-1523`

## 证据

```python
if len(data_list) == 1:
    return {
        "mean": data_list[0],
        "std": 0.0,
        "k": float("inf") if data_list[0] != value else 0.0,
        "chebyshev_upper_bound": 0.0,
        "min_probability_in_range": 1.0,
        "deviation": value - data_list[0],
        "message": "数据只有一个元素，标准差为0",
    }
# ...
if k <= 1:
    chebyshev_upper_bound = 1.0
    min_probability_in_range = 0.0
else:
    chebyshev_upper_bound = 1 / (k**2)
    min_probability_in_range = 1 - chebyshev_upper_bound
# ...
result = {
    "mean": mean,
    "std": std,
    "k": k,
    "chebyshev_upper_bound": chebyshev_upper_bound,
    "min_probability_in_range": min_probability_in_range,
    "deviation": deviation,
}
# 添加人类可读的解释
if k <= 1:
    result["message"] = (
        f"数值 {value:.4f} 距离均值 {mean:.4f} 只有 {k:.4f} 个标准差（在 1σ 范围内），切比雪夫不等式不提供有用信息"
    )
else:
    result["message"] = (
        f"数值 {value:.4f} 距离均值 {mean:.4f} 约 {k:.4f} 个标准差。"
        f"根据切比雪夫不等式，至少有 {min_probability_in_range:.2%} 的数据"
        f"落在 [μ - {k:.4f}σ, μ + {k:.4f}σ] 范围内，"
        f"即 [{mean - k * std:.4f}, {mean + k * std:.4f}] 区间。"
        f"超出此范围的数据比例不超过 {chebyshev_upper_bound:.2%}。"
    )
```

同文件还有 AUTOA classmethod 副本（约 2535 起，message 写入约 2638/2642），结构相同。

## 为什么是问题

`calculate_chebyshev_probability` 返回的 dict 装配了大量诊断字段：`message`、`min_probability_in_range`、`deviation`、`mean`、`std`、`k`。全项目 Grep（含 `test_autoTrade_pm.py`、`autoTrade.py`、`autoTrade_papi.py`、`test_backtest_autoa_parity.py`、`autoBN_v2.py`、`calibrate_short_oi_drawdown.py`）显示所有运行时调用方只取 `["chebyshev_upper_bound"]`，没有任何代码读其余字段；`message` 仅有写入，无 log/print/反射消费。docstring 示例不算运行时消费者；`calibrate_short_oi_drawdown.py` 独立重写算法，不调用本方法。

其中 `message` 字符串拼装（约 1511-1523）以及专为 message 服务的 `min_probability_in_range`、第二次 `k<=1` 分支，属于纯死代码开销。`mean`/`std`/`k`/`deviation` 作为中间量计算 upper_bound 仍需要，但塞进返回 dict 的部分对执行路径无用。两份实现（实例方法约 1422 与 AUTOA classmethod 约 2535）存在相同死字段，印证是复制粘贴的诊断壳，不是被某条路径承重。

## 影响面

不修则每次切比雪夫计算都多做无用字段装配与 f-string 拼装，热路径上属于可避免的冗余；诊断壳跨文件复制（`autoTrade.py` / `autoTrade_papi.py` / `autoBN_v2.py`）也会持续放大维护面。

修了会碰到生产/测试调用点（均只读 `["chebyshev_upper_bound"]`）：

- AUTOBN：`tokenDemo/autoTrade_pm.py:1212-1215`（多信号）、`:1910-1911`（空信号）
- AUTOA：`tokenDemo/autoTrade_pm.py:3292-3295`（成交量切比雪夫）
- 同形态：`tokenDemo/autoTrade.py:946-949`、`1055-1058`、`2800-2803`；`tokenDemo/autoTrade_papi.py:993-996`、`1102-1105`、`2839-2842`
- 测试：`tokenDemo/test_backtest_autoa_parity.py:56` 只取 upper_bound；`tokenDemo/test_autoTrade_pm.py:1942-1943` mock 返回值仅含 `{"chebyshev_upper_bound": 0.001}`

按「至少删 message / min_probability_in_range」的安全子集改，正常路径、单元素路径、std==0 路径、k<=1 路径的 `chebyshev_upper_bound` 数值与现行为一致，调用约定不变。

## 建议改法

生产路径可只返回 `chebyshev_upper_bound`（或直接返回 float）；至少删掉 `message` 拼装与 `min_probability_in_range`。`mean`/`std`/`k`/`deviation` 仍作局部中间量算 upper_bound，不必再写入返回 dict。

若保留诊断 dict：

- 把 `message` 改成可选/懒生成，默认路径不拼装
- 同步处理实例方法与 AUTOA classmethod 两份实现，避免只清一边
- 若进一步改成直接返回 float，会破坏现有 `["chebyshev_upper_bound"]` 调用约定，需一并改调用点；本发现优先推荐不破坏约定的安全子集

不在本审计阶段写完整实现，交由 `cs-refactor` 落地。

## 对抗验证记录

视角一：生产/测试调用点全部只读 `["chebyshev_upper_bound"]`；`message` / `min_probability_in_range` / `deviation` / `mean` / `std` / `k` 作为返回 dict 字段全项目无运行时读取；按建议安全子集改不会改变任何执行路径的 upper_bound 数值。结论：无用代码判断正确，不推翻。

视角二：证据属实——`tokenDemo/autoTrade_pm.py:1456-1523` 存在单元素早退 dict、k<=1 时 min_probability_in_range、result 装配及 1511-1523 的 message 拼装（逻辑与片段一致，行号无偏移）；两份实现同形死字段印证复制粘贴诊断壳。非 ruff 机械复述；P2/high 定级合理，不推翻。
