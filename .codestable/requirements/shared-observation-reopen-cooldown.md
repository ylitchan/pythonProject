---
doc_type: requirement
slug: shared-observation-reopen-cooldown
pitch: 平仓后按各市场时间规则可靠阻止同一标的过早重开，并在程序重启后继续生效
status: current
last_reviewed: 2026-07-25
implemented_by: [2026-07-25-shared-observation-reopen-cooldown]
tags: [observation, cooldown, autobn, autoa, persistence]
---

# 统一观察状态重开冷却

## 用户故事

- 作为实盘策略使用者，我希望同一标的平仓后不会立即被残留观察信号重新开仓。
- 作为长期运行者，我希望冷却状态随观察记录持久化，进程重启后仍然有效。
- 作为跨市场策略使用者，我希望数字货币按连续24小时、A股按实际交易日计算，而不是混用自然日。

## 为什么需要

AUTOBN原先把最近平仓时间保存在独立状态字典中，AUTOA没有同等保护。平行状态源容易在重启、迁移或策略复用时产生不一致，A股若使用自然日又会把周末和法定休市错误计入冷却。

## 怎么解决

共用Observation保存可选的最早开仓时间戳。AUTOBN完整平仓后写入确认清仓时间加24小时；AUTOA平仓后查询实际A股交易日历，完整空过第一个后续交易日，从第二个后续交易日开始允许开仓。所有开仓入口在执行原策略判断前读取该字段。

## 边界

- 新观察没有冷却时字段为null，旧Observation JSON缺字段时兼容为null。
- 只有完整清仓或确认交易所仓位为零时设置冷却；部分平仓不设置。
- AUTOA周末和法定休市日不计，日历不足时不退化为48小时或工作日近似。
- 正常状态满足Position存在则Observation存在；不为异常缺失补造Observation，也不修改Observation删除逻辑。
- 不改变AUTOBN与AUTOA的其他入场、出场、观察超时和风险规则。
