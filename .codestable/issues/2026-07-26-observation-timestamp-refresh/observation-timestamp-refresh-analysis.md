---
doc_type: issue-analysis
issue: 2026-07-26-observation-timestamp-refresh
status: confirmed
root_cause_type: state-pollution
related: [observation-timestamp-refresh-report.md]
tags: [autobn, autoa, observation, timestamp, state]
---

# Observation 时间戳被非观察条件刷新 根因分析

## 1. 问题定位

| 关键位置 | 说明 |
|---|---|
| `tokenDemo/autoTrade_pm.py:124-128` | `earliest_open_timestamp` 独立承担重开冷却，证明 `timestamp` 不需要兼任开仓冷却。 |
| `tokenDemo/autoTrade_pm.py:1861-1884` | 持仓止盈/止损为 0 时初始化 ATR，同时无条件新建 Observation 并写入当前时间。 |
| `tokenDemo/autoTrade_pm.py:2003-2007` | Observation 超时使用 `timestamp` 计算，非观察刷新会延长有效期。 |
| `tokenDemo/autoTrade_pm.py:2101-2160` | BZ/BD 开仓成功后把 `open_info.timestamp` 改为当前时间，目的却是同日重复开仓防护。 |
| `tokenDemo/autoTrade_pm.py:2172-2184` | BD 再次满足明确的刷新条件后更新价格和时间，属于合法刷新。 |
| `tokenDemo/autoTrade_pm.py:2204-2228` | BZ/BD 首次满足观察条件时创建 Observation，属于合法初始化。 |
| `tokenDemo/autoTrade_pm.py:3284-3412` | AUTOA 开仓只读取并写回 Observation，不给 `timestamp` 赋值。 |
| `tokenDemo/autoTrade_pm.py:3480-3497` | AUTOA 进入当日涨停池时创建或刷新 Observation，属于合法观察事件。 |

## 2. 失败路径还原

**正常路径**：标的满足 BZ、BD 或 AUTOA 涨停池观察条件 → 创建或更新 Observation →
`timestamp` 记录本次观察条件成立时间 → 超时和同日去重以该时间为准。

**失败路径 A（开仓成功）**：既有 Observation 推导出开仓信号 → 交易所开仓成功 →
代码为了避免同日再次开仓，把 `timestamp` 改为开仓时间 → 观察有效期和日期判断改从
开仓时刻计算。

**分叉点 A**：`tokenDemo/autoTrade_pm.py:2157-2160` — 非观察事件污染了观察时间。

**失败路径 B（ATR 初始化）**：已有持仓止盈或止损为 0 → 持仓管理根据 ATR 补值 →
代码同时从 Position 字段重新构造 Observation → `timestamp` 变为当前时间，并丢弃原
Observation 上未被构造器显式传入的状态。

**分叉点 B**：`tokenDemo/autoTrade_pm.py:1875-1884` — 持仓兼容初始化与观察状态重建被
错误绑定。

## 3. 根因

**根因类型**：状态污染。

**根因描述**：`Observation.timestamp` 同时被当作“最近观察条件成立时间”和“最近开仓/
持仓初始化时间”。开仓重复保护、ATR 持仓初始化本应由各自状态处理，却通过修改或重建
Observation 间接实现，导致字段语义混杂。当前已有 `earliest_open_timestamp` 独立承载
平仓后重开冷却，继续修改 `timestamp` 已无正当状态职责。

**是否有多个根因**：是。

- 主因：开仓成功分支显式刷新既有 Observation 的 `timestamp`。
- 次因：ATR 初始化分支整对象重建 Observation，将当前时间和 Position 的部分字段覆盖
  到观察状态。

## 4. 影响面

- **影响范围**：开仓刷新公共分支同时影响 AUTOBN BZ 开多和 BD 开空；ATR 初始化影响
  所有止盈/止损为 0 的 AUTOBN 已有持仓。
- **潜在受害模块**：Observation 超时清理、同 UTC 日观察去重、平仓后保留 Observation
  的重开流程，以及依赖 `bz_reference_high` / `earliest_open_timestamp` 的后续判断。
- **AUTOA**：开仓和平仓冷却不修改 `timestamp`，无需改生产逻辑；涨停池刷新是合法
  观察事件，应补回归守护但不能删除。有效期已是30天，N在同一BZ Observation上演进，
  完整平仓保留Observation，均符合更新后的需求。
- **生命周期差异**：AUTOBN当前所有Observation共用7天超时，完整平仓统一保留并写24小时
  冷却；用户确认应改为BZ有效24小时且平仓后保留冷却，BD有效7天且完整平仓后删除。
- **数据完整性风险**：有。ATR 初始化重建会丢失旧 Observation 中
  `bz_reference_high`、`earliest_open_timestamp` 等未显式传入字段。
- **严重程度复核**：维持 P1。它会稳定改变交易状态寿命及冷却字段完整性，但不导致
  全系统不可用。

## 5. 修复方案

### 方案 A：删除两处非观察写入（推荐）

- **做什么**：
  - 开仓成功后继续清理临时策略标签并写回 Observation，但删除 `timestamp` 赋值；
  - ATR 初始化只更新并写回 Position 的止盈止损，不再创建或覆盖 Observation；
  - AUTOBN超时按策略拆分：BZ为24小时，BD为7天；历史或人工形成的混合 `[BZ, BD]` 记录按更短的BZ有效期处理，避免过期BZ信号沿用BD的7天寿命；
  - 确认完整平仓后，BD删除Observation；BZ仅在Observation仍处于24小时有效期内时保留并写24小时冷却，已经过期则直接删除；
  - BZ完整平仓时若Observation异常缺失，不补造Observation，也不能阻止本地Position清理；
  - 补 BZ/BD 成功开仓、ATR 初始化、策略超时、完整/部分平仓、Observation缺失、混合策略标签、AUTOA N/BZ共享与平仓回归测试。
- **优点**：直接恢复字段单一语义；改动最小；保留原 Observation 全部字段；不引入新状态。
- **缺点 / 风险**：删除旧的“同日重复开仓”隐式保护，但当前只要 Position 仍存在就不会
  进入开仓分支；完整平仓后的保护已由 `earliest_open_timestamp` 承担。
- **影响面**：`tokenDemo/autoTrade_pm.py` 与 `tokenDemo/test_autoTrade_pm.py`。

### 方案 B：新增独立的最近开仓时间字段

- **做什么**：新增 `last_open_timestamp`，把开仓成功时的当前时间写入该字段，并将所有
  同日防重逻辑改为读取新字段；ATR 初始化仍停止重建 Observation。
- **优点**：显式保留最近开仓时间，可用于未来独立规则。
- **缺点 / 风险**：当前没有实际消费者，属于额外状态和持久化契约；增加旧 JSON 兼容、
  测试和维护成本，违反最小修复原则。
- **影响面**：模型、持久化状态、生产逻辑和测试。

### 方案 C：保留 ATR 重建但复制原字段与时间戳

- **做什么**：ATR 初始化时重建 Observation，但从原对象复制 `timestamp` 及所有扩展字段；
  开仓成功仍删除时间戳赋值。
- **优点**：形式上接近旧流程。
- **缺点 / 风险**：持仓管理继续无必要地重建观察对象；未来新增字段时仍容易遗漏，根因未
  从结构上消除。
- **影响面**：两个生产分支及测试。

### 推荐方案

**推荐方案 A**。它把 `Observation.timestamp` 收紧为唯一语义，删除两处无正当职责的
状态副作用；AUTOA 与所有真实观察写入保持不变，也不会引入没有消费者的新字段。
