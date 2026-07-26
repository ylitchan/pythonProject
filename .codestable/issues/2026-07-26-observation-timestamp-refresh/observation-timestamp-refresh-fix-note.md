---
doc_type: issue-fix
issue: 2026-07-26-observation-timestamp-refresh
status: fixed
severity: P1
summary: Observation时间只由真实观察条件刷新，并按AUTOA、BZ和BD分别管理生命周期与完整平仓行为
tags: [autobn, autoa, observation, timestamp, lifecycle, cooldown]
---

# Observation 时间戳与生命周期 Fix Note

## 问题与目标

AUTOBN 在开仓成功和持仓 ATR 初始化时会刷新或重建 Observation，使 `timestamp` 不再表示真实观察条件成立时间，并可能丢失观察记录中的扩展字段。与此同时，AUTOBN BZ 与 BD 原先共用7天有效期和相同的平仓后冷却行为，不符合两类信号的实际生命周期。

目标是将 `timestamp` 收紧为唯一语义：仅在真实观察条件成立时创建或刷新；`earliest_open_timestamp` 仅承担重开冷却，不延长观察寿命。AUTOA 保持30天有效期、N复用BZ Observation及完整平仓后保留；AUTOBN BZ改为24小时，BD保持7天且完整平仓后删除。

## 修复

- `tokenDemo/autoTrade_pm.py:301-302`：拆分AUTOBN观察有效期常量，BZ为24小时，BD为7天。
- `tokenDemo/autoTrade_pm.py:856-874`：完整平仓后按策略处理Observation：
  - BD删除Observation，不写冷却；
  - BZ Observation缺失时不补造，仍允许清理本地Position；
  - BZ Observation已超过24小时则删除；
  - BZ Observation仍有效时保留原`timestamp`，只写24小时重开冷却。
- `tokenDemo/autoTrade_pm.py:2004-2012`：观察超时按策略选择；含BZ的混合历史标签按更短的24小时处理，防止过期BZ信号沿用BD的7天寿命。
- AUTOBN ATR初始化只更新Position止盈止损，不再重建Observation。
- `tokenDemo/autoTrade_pm.py:2161-2162`：BZ/BD开仓成功后不再把Observation时间改成开仓时间。
- AUTOA生产行为保持不变，仅修正其观察有效期注释为30天；涨停池新增/刷新仍是合法的真实观察写入。
- 更新 `.codestable/requirements/shared-observation-reopen-cooldown.md` 与 `VISION.md`，记录各策略的有效期、冷却和完整平仓边界。

## 验证

新增和增强的回归场景覆盖：

- BZ、BD成功开仓均保留原Observation时间；
- ATR初始化保留原时间、BZ参考高点和重开冷却字段；
- BZ 24小时、BD 7天，混合`[BZ, BD]`按BZ短期限清理；
- BZ正常完整平仓保留有效Observation并写冷却，过期Observation直接删除；
- BZ Observation缺失时完整平仓仍清理Position；
- BD在下单前已归零、下单后确认归零、异常后复查归零三类路径均删除Observation；
- BD部分平仓不修改Observation；
- AUTOA N继续复用BZ Observation，开仓和平仓均不刷新观察时间。

完整测试：

```text
uv run python -m unittest tokenDemo.test_autoTrade_pm
```

结果：80项测试全部通过。日志中的“文件被占用”堆栈来自既有平仓记录错误路径测试，最终测试状态为`OK`，不是本次回归。

静态检查：

```text
uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py
```

结果：`All checks passed!`

写入点复核确认，生产代码中Observation的`timestamp`只在以下真实观察事件中赋值：AUTOBN BZ首次入池、BD首次入池、BD条件续期，以及AUTOA涨停池新增/刷新。

## 影响范围

生产代码仅修改 `tokenDemo/autoTrade_pm.py`；测试仅修改 `tokenDemo/test_autoTrade_pm.py`。AUTOA既有30天生命周期、N/BZ共享、交易日冷却及涨停池刷新逻辑未改变。部分平仓、平仓后查询失败或仍有仓位时不改变Observation。

## 对抗审查

对时间字段语义、策略超时边界和完整平仓状态机进行对抗检查后，补齐并验证了三个边界：Observation缺失容错、混合BZ/BD标签采用短期限、过期BZ在完整平仓时直接删除而不被冷却续命。

## 遗留

- `tokenDemo/test_backtest_autoa_parity.py` 当前只打印差异，不通过断言或非零退出表达失败；不在本次issue范围，可另行处理。
- `.codestable/requirements/VISION.md` 索引中的 `autoa-bz-pullback-entry.md` 当前缺失；不在本次issue范围，未补造。
- `tokenDemo/autoTrade.py` 与 `tokenDemo/autoTrade_papi.py` 不在用户指定范围，本次未同步修改。
- 未提交或推送；版本控制动作等待用户明确授权。
