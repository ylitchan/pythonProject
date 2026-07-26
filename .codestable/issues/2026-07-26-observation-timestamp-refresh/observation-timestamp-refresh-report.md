---
doc_type: issue-report
issue: 2026-07-26-observation-timestamp-refresh
status: confirmed
severity: P1
summary: AUTOBN 的非观察事件会刷新或重建 Observation 时间戳，改变观察有效期语义
tags: [autobn, autoa, observation, timestamp, state]
---

# Observation 时间戳被非观察条件刷新 Issue Report

## 1. 问题现象

共享 `Observation.timestamp` 应表示标的最近一次实际满足观察条件的时间，但 AUTOBN
在开仓成功以及持仓 ATR 初始化时，也会把该字段更新为当前时间或以当前时间重建
Observation。这会令观察记录看起来像刚刚重新满足过观察条件。

AUTOA、AUTOBN BZ 开多和 BD 开空均需纳入核查，确保所有观察模型遵循同一语义。

## 2. 复现步骤

### 场景 A：AUTOBN 开仓成功

1. 准备一个已有 BZ 或 BD Observation，其 `timestamp` 早于当前时间。
2. 让对应开仓确认条件成立，并令 `open_bn_position()` 返回成功。
3. 读取开仓后 `OBSERVATIONS[symbol].timestamp`。
4. 观察到：时间戳被改成当前开仓时间，而不是保留最近一次满足观察条件的时间。

### 场景 B：AUTOBN ATR 初始化

1. 准备一个已有 Position，令 `take_profit == 0` 或 `stop_loss == 0`，并使 ATR 大于 0。
2. 同时准备包含既有时间戳及扩展字段的 Observation。
3. 执行持仓管理。
4. 观察到：代码以当前时间重建 Observation，原时间戳被覆盖，其他扩展字段也可能丢失。

复现频率：稳定。

## 3. 期望 vs 实际

**期望行为**：`Observation.timestamp` 只能在标的实际满足观察条件时创建或刷新；
AUTOBN 开仓、持仓管理、AUTOA 开仓和平仓冷却等非观察事件均不得修改它。

**实际行为**：AUTOBN 开仓成功会无条件刷新既有 Observation 的时间戳；持仓 ATR
初始化会用当前时间重建 Observation。AUTOA 开仓和平仓冷却经核查不会修改该字段，
AUTOA 当日涨停池新增/刷新、AUTOBN BZ/BD 首次入池及 BD 条件续期属于合法写入。

## 4. 环境信息

- 涉及模块 / 功能：AUTOBN BZ/BD 观察与开仓、AUTOBN 持仓管理、AUTOA 观察与开仓
- 相关文件 / 函数：
  - `tokenDemo/autoTrade_pm.py:_manage_position`
  - `tokenDemo/autoTrade_pm.py:rzq_token`
  - `tokenDemo/autoTrade_pm.py:AUTOA.on_observations`
  - `tokenDemo/autoTrade_pm.py:AUTOA.filter_stocks`
- 运行环境：当前开发分支
- 其他上下文：共享 Observation 另有 `earliest_open_timestamp` 专门承载平仓后重开冷却，
  不应由 `timestamp` 兼任开仓或冷却状态。

## 5. 严重程度

**P1** — 非观察事件会延长观察有效期并改变同日去重判断；ATR 初始化还可能覆盖
Observation 的其他状态字段，影响后续真实交易决策。

## 备注

代码核查确认的合法写入包括：

- AUTOBN BZ 首次满足观察条件时创建；
- AUTOBN BD 首次满足及后续刷新条件时创建/刷新；
- AUTOA 标的进入当日涨停池时创建或刷新。

确认的异常写入只有 AUTOBN 两处：开仓成功后的显式赋值，以及 ATR 初始化时的重建。
