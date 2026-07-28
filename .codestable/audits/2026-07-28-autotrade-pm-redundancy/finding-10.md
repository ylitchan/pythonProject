---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 10
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
summary: SHORT 分支对 completed_oi 的二次判空冗余
tags: [autotrade-pm, redundant-guard]
---

# SHORT 分支对 completed_oi is None 的二次判空恒与 realtime_oi 同步

## 位置

`tokenDemo/autoTrade_pm.py:1143-1144`

## 证据

```python
                    realtime_oi, completed_oi = await self._get_bd_oi_windows(
                        symbol, dtn
                    )
                    if realtime_oi is None or completed_oi is None:
                        return False, None, None
                    oi_5m_last = realtime_oi[-1]
                    oi_peak = max(completed_oi)
```

## 为什么是问题

`_get_bd_oi_windows`（`tokenDemo/autoTrade_pm.py:1109-1124`）只有两条失败路径，且都是成对 `return None, None`：一是 `oi_1d` 缺失或长度小于 `OI_QUERY_LIMIT`；二是 `oi_5m` 为假值。成功路径先用已通过长度校验的 `oi_1d` 构造 `completed_oi`（至少 30 根），再 `realtime_oi = completed_oi + [最新 5m]`，最后成对返回两个非空列表。中间若 `float(...)` 或取键失败会抛异常，由 `check_side` 外层 `try` 接住，不会以“一空一非空”返回。

因此在任意可达生产路径上（含首次无缓存、API 失败回退缓存、空数据、异常）都有 `realtime_oi is None ⇔ completed_oi is None`。`or completed_oi is None` 在 `realtime_oi is None` 已覆盖失败路径后永远不提供额外否决信息，属于审计定义下的冗余判断，而不是对未来契约漂移的必要承重。

## 影响面

不修：代码可读性下降，读者会误以为存在“只返回一侧为 None”的契约；后续改动若照抄双判空，会继续扩散冗余守卫。

修了行为不变：失败仍 early-return `(False, None, None)`；成功仍执行 `oi_5m_last = realtime_oi[-1]` / `oi_peak = max(completed_oi)`。

相关调用点：
- `check_side` SHORT（`tokenDemo/autoTrade_pm.py:1140-1144`）：唯一同时消费两个返回值，也是本条判断所在
- `_is_bd_observation`（`tokenDemo/autoTrade_pm.py:1890`）与观察刷新（`tokenDemo/autoTrade_pm.py:2124`）：`oi_window, _ = ...`，只看 realtime，与 `completed_oi is None` 无关
- `autoTrade.py` / `autoTrade_papi.py`：各自独立 AUTOBN，无此方法、无覆盖/子类
- 测试 `tokenDemo/test_autoTrade_pm.py`：`make_autobn` 成对传入 `(oi_window, completed_oi)`，不可用场景统一 mock `(None, None)`，无 `(list, None)` / `(None, list)` 非对称 mock 依赖此双判空；直测 `_get_bd_oi_windows` 也只断言成功双 list 或失败 `(None, None)`

## 建议改法

改为只判断 `realtime_oi is None`（或 `not realtime_oi`），去掉 `completed_oi is None` 分支。例如：

```python
if realtime_oi is None:
    return False, None, None
```

不要改 `_get_bd_oi_windows` 的返回契约；不要在此处补“防御性”非对称分支。

## 对抗验证记录

对照生产实现与全部调用/测试后，该发现成立，不是误报。视角一：核对 `_get_bd_oi_windows` 仅两处失败路径成对 `return None, None`，成功路径成对返回两个非空列表，故 `or completed_oi is None` 无额外信息。视角二：核对调用点与测试 mock 均无非对称依赖，且未撞已定案项（非四个行情缓存协议、非 blend 配对、非 `or []` 刻意统一）；非 ruff 可机械复述项，需语义分析配对返回。定级 maintainability / P2 / high 合理，行号无偏移。
