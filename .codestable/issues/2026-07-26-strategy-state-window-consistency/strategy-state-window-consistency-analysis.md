---
doc_type: issue-analysis
issue: 2026-07-26-strategy-state-window-consistency
status: confirmed
root_cause_type: logic
related: [strategy-state-window-consistency-report.md]
tags: [autobn, autoa, observation, oi, kline, window, partial-close]
---

# 策略状态与数据窗口不一致根因分析

## 1. 问题定位

| 关键位置 | 说明 |
|---|---|
| `tokenDemo/autoTrade_pm.py:854-871` | 完整平仓后的 Observation 处理按 BD/BZ 分叉：BD 删除，BZ 未过期时写入24小时重开时间，造成 BZ 生命周期与24小时有效期重叠。 |
| `tokenDemo/autoTrade_pm.py:978-993` | `calc_stop_profit_loss()` 已按方向返回 `(take_profit, stop_loss)`，调用方却再次交换 SHORT 返回值。 |
| `tokenDemo/autoTrade_pm.py:1026-1067` | 5m/1h OI 请求固定30条，但获取边界未验证数量；短窗口会进入下游。缓存也会保存并复用短窗口。 |
| `tokenDemo/autoTrade_pm.py:1069-1099` | 日 OI 使用 `limit=OI_QUERY_LIMIT + 1`，与固定请求30条的契约冲突；过滤后只判断非空。 |
| `tokenDemo/autoTrade_pm.py:1101-1122` | 日 OI 虽要求至少30条，却用 `[-30:]` 后再用 `[-29:]` 拼5m，主动丢掉第一条完成日数据；5m OI也只判断非空。 |
| `tokenDemo/autoTrade_pm.py:1160-1168` | 由 `longShortRatio` 推导多头占比时保留接口不可能产生的 `<= -1` 分支，并迫使下游处理 `None`。 |
| `tokenDemo/autoTrade_pm.py:1180-1191` | LONG 的1h OI下游仅要求至少1条及局部切比雪夫样本数，掩盖上游固定30条请求契约。 |
| `tokenDemo/autoTrade_pm.py:1258-1288` | 日K固定请求30条，但 `get_kline()` 不验证完整性，调用方可收到1至29条。 |
| `tokenDemo/autoTrade_pm.py:1290-1355` | 1h多空比固定请求30条却不检查数量；请求失败还会退回可能不足30条的旧缓存。5m请求1条失败或过期时，仍返回1h数据，调用方会把1h尾项误当作最新5m项。 |
| `tokenDemo/autoTrade_pm.py:1924-1948` | BD实时OI仍按30点固定切片，接收新的31点窗口后会丢弃最早数据，baseline 未使用完整返回窗口。 |
| `tokenDemo/autoTrade_pm.py:1967-1972` | AUTOBN日K固定请求30条，但入口只要求 `MIN_KLINE_FOR_ANALYSIS=4`。 |
| `tokenDemo/autoTrade_pm.py:1979,2151-2159,2176-2188` | `bd_deleted_this_round`、旧BD策略及同UTC日判断共同组成全局写入闸门，使本轮真实新观察无法按新旧关系覆盖。 |
| `tokenDemo/autoTrade_pm.py:2190-2217` | BZ/BD候选本来已通过 `if/elif` 保持BZ优先，但被外层 `can_set_observation` 整体跳过。 |
| `tokenDemo/autoTrade_pm.py:2565-2575` | AUTOA高开检查自行要求至少2根K线，是统一30根入口建立后应删除的重复局部门槛。 |
| `tokenDemo/autoTrade_pm.py:3069-3105` | AUTOA持仓行情入口只判断空表，随后又以 `len(hist)>1` 为成交量兜底，29根等不完整数据仍会继续。 |
| `tokenDemo/autoTrade_pm.py:3273-3360` | AUTOA观察行情入口只判断空表；后续再以 `len(hist_volume)>=30` 包裹主逻辑，数据完整性没有成为统一入口契约。 |

## 2. 失败路径还原

### Observation 覆盖

**正常路径**：本轮行情满足真实观察条件 → 先判断BZ、否则判断BD → 新 Observation 带本轮时间戳覆盖同标的旧记录。

**失败路径**：旧记录含BD、旧BZ与本轮同UTC日，或旧BD刚因量峰被删 → `can_set_observation=False` → BZ/BD候选判断整段不执行 → 更新的真实观察丢失。

**分叉点**：`tokenDemo/autoTrade_pm.py:2177-2188` — 用旧状态和删除过程控制本轮候选写入，而不是让本轮真实条件决定最终状态。

### 完整平仓与SHORT余仓

**正常路径**：交易所确认余仓为0 → 删除 AUTOBN Observation；仍有SHORT余仓 → 将方向正确的 `(TP, SL)` 直接写回。

**失败路径**：BZ归零进入冷却分支保留Observation；SHORT仍有余仓时再次交换已经方向化的返回值，得到上方TP和下方SL。

**分叉点**：`tokenDemo/autoTrade_pm.py:855-871`、`tokenDemo/autoTrade_pm.py:985-991`。

### 固定窗口与BD OI

**正常路径**：固定请求N条 → 只在恰有完整N条时返回；BD用30条完成日OI并追加1条新鲜5m OI形成31点实时窗口，baseline/old/recent覆盖全部31点。

**失败路径**：获取器缓存并返回短数据 → 下游用更小的局部门槛继续；日OI额外请求31条后截30条，再主动截成29条拼5m；多空比缺少新鲜5m时把1h尾项当5m使用。

**分叉点**：各获取边界没有实现“请求数量就是最低完整数量”的统一契约，且 `_get_bd_oi_windows()` 和 `_is_bd_observation()` 各自二次切片。

### AUTOA行情

**正常路径**：观察和持仓入口取得行情 → 少于30根立即返回 → 后续逻辑默认K线与成交量均完整。

**失败路径**：入口只拒绝空表 → 局部函数分别用2根、30根或成交量兜底判断 → 不完整窗口可能部分参与平仓、ATR或形态判断。

**分叉点**：`tokenDemo/autoTrade_pm.py:3098-3105` 与 `tokenDemo/autoTrade_pm.py:3315-3327`。

## 3. 根因

**根因类型**：逻辑错误、状态污染、数据格式契约不一致。

**根因描述**：代码把“旧状态是否允许写入”和“本轮是否形成新观察”混成同一个闸门；把固定请求数量仅当作API参数而非返回契约；并在不同消费者中以局部最小长度、额外切片和方向二次转换补偿。这些补偿互不共享同一语义，最终分别造成新状态被旧状态阻挡、完整窗口被截断、短窗口被放行以及SHORT方向反置。

**是否有多个根因**：是。

1. **主因：边界契约未集中在数据入口**——固定limit没有在获取器或统一行情入口验证，消费者自行采用不同局部门槛。
2. **主因：Observation候选选择与旧状态生命周期耦合**——旧策略、旧日期和删除过程标志阻挡本轮真实候选。
3. **次因：返回契约被调用方重复解释**——SHORT TP/SL已方向化后又交换，BD完整数据再次切片。
4. **次因：历史需求残留**——BZ完整平仓冷却和不可达多空比分支在当前业务规则下已失去意义。

## 4. 影响面

- **影响范围**：不仅影响报告中的单次信号；所有AUTOBN BZ/BD观察切换、完整平仓后的再观察、依赖日K/OI/多空比的入场与止损，以及AUTOA观察/持仓行情计算均可能受影响。
- **潜在受害模块**：AUTOBN `rzq_token()`、`check_side()`、BD Observation、OI止损、ATR与部分止盈；AUTOA `on_observations()`、`on_positions()`、BZ/N形态与成交量止损。
- **数据完整性风险**：有。Observation可能保留过时策略或漏写更新策略；Position可能保存方向反置的TP/SL；短行情窗口可能形成不可比较的统计结果。不会修改交易所历史数据，但会污染本地策略状态并影响后续交易决策。
- **严重程度复核**：维持 **P1**。该问题可直接改变候选方向、风控线和交易判断，但并非所有标的或每轮都会触发，且没有证据表明核心系统全面不可用，未达到P0。

## 5. 修复方案

### 方案 A：入口契约与候选决策统一（推荐）

- **做什么**：
  - 删除 `bd_deleted_this_round` 和 `can_set_observation`；每轮直接按BZ优先、BD次之计算真实新候选，成立即覆盖旧Observation。
  - AUTOBN确认完整平仓后无条件删除对应Observation；部分平仓、查询失败或仍有余仓不变。
  - 日K、5m/1h/1d OI、1h ratio和最新5m ratio在各自获取边界验证固定数量；日OI API固定请求30条。
  - BD窗口用完整30条日OI加最新5m形成31点，`baseline=recent/old之前全部点`。
  - AUTOA `on_observations()`、`on_positions()` 获取行情后统一要求至少30根，删除后续2根/30根等重复数量guard。
  - LONG/SHORT直接写入 `calc_stop_profit_loss()` 返回的TP/SL；删除 `lsr<=-1` 分支。
- **优点**：直接修复各根因；契约集中、消费者语义一致；改动仍限于现有函数，不引入抽象或新状态。
- **缺点 / 风险**：既有测试夹具若只提供最小样本会大量暴露，需要统一补齐到真实请求数量；短旧缓存将不再被接受。
- **影响面**：`tokenDemo/autoTrade_pm.py`、`tokenDemo/test_autoTrade_pm.py`、本issue文档及Observation需求文档。

### 方案 B：仅在各消费点补条件

- **做什么**：保留现有获取器和状态闸门，在 `rzq_token()`、`check_side()`、`_is_bd_observation()`、AUTOA各分支逐处增加长度判断和覆盖例外；为SHORT单独修正交换；为BZ完整平仓单独增加删除分支。
- **优点**：单个函数表面改动较小，旧获取器行为不变。
- **缺点 / 风险**：继续允许短数据进入缓存；多个消费者会重复数量判断，容易再次出现29/30、1/30等语义漂移；Observation覆盖仍依赖特殊例外，违背“谁新谁覆盖”；不满足用户要求的统一入口与下游不重复判断原则。
- **影响面**：代码文件相同，但分支更多、维护风险更高。

### 方案 C：引入统一行情窗口对象

- **做什么**：新增类型封装请求数量、完成窗口、实时点和新鲜度，AUTOBN/AUTOA消费者只接收校验后的窗口对象；Observation候选也抽成显式优先级选择器。
- **优点**：长期类型契约最强，未来较难误用窗口。
- **缺点 / 风险**：属于结构性重构，会引入新抽象并扩大测试和迁移范围；超出本次最小issue修复边界。
- **影响面**：可能新增文件并改动更多调用方，不符合当前仅定点修改的范围。

### 推荐方案

**推荐方案 A**。它把固定数量校验放回数据边界、把新观察选择从旧状态中解耦，并遵守现有函数的方向返回契约；既完整满足已确认规则，又不引入方案C的结构性重构。方案B虽然局部改动看似少，但会保留本次问题的共同根因。
