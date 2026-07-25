# bd-two-cohort-cost 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-07-25
> 关联方案 doc：`.codestable/features/2026-07-25-bd-two-cohort-cost/bd-two-cohort-cost-design.md`

## 1. 接口契约核对

- [x] `AUTOBN._get_bd_oi_windows`：29个已完成日级OI与最新新鲜5m OI组成入池窗口，同时返回30个已完成日线OI作为开仓基准；缺失、过期或未来5m点返回无有效窗口。
- [x] `Observation`与`Position`模型均未增加OI字段，旧JSON及BZ/AUTOA状态结构不变。
- [x] `_get_oi_1d_data`按当前UTC日的数据可得边界筛选，不再依赖进程本地08:00精确相等。
- [x] 方案流程图各节点均在`rzq_token`、`_is_bd_observation`与`check_side`落地。

## 2. 行为与决策核对

- [x] 首次入池按前20根基线、中间7根旧成本和最近3根高位窗口判断。
- [x] 旧7根OI峰值切比雪夫严格低于5%，最近3根OI峰值严格超过旧7根。
- [x] 最近3根含并列或更高30日量峰时拒绝首次入池；已有BD观察在未开仓后遇当日新天量删除且同轮不重建。
- [x] 不满足刷新且无新天量时保留原观察；刷新只更新时间和顶部价格，不修改模型。
- [x] 开仓以30个已完成日线OI峰值为基准，最新5m OI回撤至少10%；价格方向与开多镜像，要求当前价严格低于昨收。
- [x] AUTOBN观察期为7天，AUTOA保持30天。
- [x] 日K价格和成交量仍直接来自`1d` K线；未引入分钟K覆盖、多空比门槛、high-to-high条件或新依赖。
- [x] 本feature无新路由、配置、定时任务、外部接口或数据库挂载点；卸载时撤回AUTOBN内部BD窗口、状态转换和7天常量即可，无外部登记残留。

## 3. 验收场景核对

- [x] **S1 数据窗口**：30个完成日线OI输入时，入池窗口取后29个并补最新5m，开仓窗口保留30个完成日线OI。证据：`test_bd_oi_windows_combine_29_daily_with_fresh_5m`。
- [x] **S2 新鲜度**：过期及未来5m时间戳均拒绝。证据：`test_bd_oi_windows_reject_stale_or_future_5m`。
- [x] **S3 数据可得边界**：UTC当日边界后的未来日线OI不参与。证据：`test_daily_oi_uses_utc_availability_boundary`。
- [x] **S4 价格顶部**：当前价未到前29日最高close时拒绝。证据：`test_bd_pool_rejects_when_price_not_at_window_high`。
- [x] **S5 量峰位置**：最近3根量峰拒绝，旧7根有效量峰可通过。证据：`test_bd_pool_rejects_fresh_volume_peak`、`test_bd_pool_accepts_two_cohort_structure`。
- [x] **S6 双层OI**：旧OI不极端或近期OI未严格超过旧峰均拒绝。证据：`test_bd_pool_rejects_mild_old_oi_accumulation`、`test_bd_pool_rejects_recent_oi_not_above_old_peak`。
- [x] **S7 开仓回撤**：10%边界通过，9%拒绝。证据：`test_short_trigger_fires_at_drawdown_threshold`、`test_short_trigger_blocked_when_oi_holds_near_peak`。
- [x] **S8 超时隔离**：AUTOBN为7天、AUTOA为30天。证据：`test_autobn_observation_timeout_is_seven_days`。
- [x] **S9 开仓失败一致性**：交易所失败不创建本地仓位并保留观察。证据：`test_failed_initial_open_does_not_create_local_position`。
- [x] **S10 回归**：`uv run python -m unittest tokenDemo.test_autoTrade_pm`运行59项，结果`OK`；模拟文件占用堆栈是既有错误路径测试。
- [x] **S11 静态检查**：`uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py`通过。

## 4. 术语一致性

- “实时30根OI窗口”仅用于入池，代码名为`realtime_oi`；“已完成日线OI窗口”用于开仓，代码名为`completed_oi`，语义无混用。
- `baseline / old / recent`对应20/7/3切片；未引入`oi_peak`模型字段。
- 价格方向继续使用现有`kline_close[-2]`昨收口径，与开多镜像。

## 5. 领域影响盘点

- [x] 新名词：双层多头成本是本策略内部解释，不新增跨模块实体或公共类型，无需写入`CONTEXT.md`。
- [x] 结构性选择：未新增模块、依赖或跨模块接口，不满足ADR条件。
- [x] 流程约束：BD的新天量失效与无未来数据规则已由feature design及requirement留档，不需另建ADR。

## 6. requirement 回写

- [x] 已backfill `.codestable/requirements/autobn-bd-two-cohort-short-confirmation.md`，状态为`current`。
- [x] 已更新`.codestable/requirements/VISION.md`的Current索引。

## 7. roadmap 回写

- [x] 非roadmap起头，方案无`roadmap`或`roadmap_item`字段，无需回写。

## 8. attention.md 候选盘点

- [x] 本feature未暴露每个后续feature都会重复遇到的环境或工具陷阱，无attention候选。

## 9. 遗留

- 多空比加载器混合1h历史与5m末项是既有审计观察，不在本feature范围。
- Binance日级OI接口历史长度有限，长期收益回测样本右截断问题仍按既有审计记录处理；本次以逐轮状态单测和无未来数据边界测试验收生产状态机，未声称旧校准脚本已升级为新模型回测。
- 未提交或推送；版本控制动作等待用户明确授权。
