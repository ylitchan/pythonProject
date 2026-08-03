# AUTOBN 两阶段止盈验收报告

> 阶段：阶段3（验收闭环）
> 验收日期：2026-08-03
> 关联方案：`.codestable/features/2026-08-03-autobn-staged-take-profit/autobn-staged-take-profit-design.md`

## 1. 接口契约核对

- [x] 第一阶段复用`tp_count`，未新增持仓字段。
- [x] 阈值为当前止盈距离1/3、1 ATR和开仓价5%的最小值。
- [x] 下一目标为当前价加/减1 ATR与当前价5%的较小距离。

## 2. 行为与决策核对

- [x] `tp_count < 1`且达标时平当前仓位70%。
- [x] 第一阶段与绝对止盈同级互斥。
- [x] 成功且有剩仓后才递增`tp_count`并提交新价格线。
- [x] 剩仓止损按触发浮盈70%收紧，不会放宽。
- [x] OI、DCA、AUTOA、行情数据源和轮询频率未改。
- [x] 挂载点反向核对与拔除沙盘通过。

## 3. 验收场景核对

- [x] 多头和空头首次达标均平70%，并写入镜像止损与下一目标。
- [x] `tp_count >= 1`不重复第一阶段。
- [x] 平仓失败不递增次数、不改价格线。
- [x] 同轮绝对目标也满足时只执行首次阶段。
- [x] 后续绝对目标继续沿用既有部分止盈。

验证：AUTOBN 61 tests / OK；全量124 tests / OK；Ruff通过。日志中的文件占用异常是既有模拟重试场景，最终结果OK。

## 4. 术语一致性

- 第一阶段止盈、下一止盈与`tp_count`职责一致，无平行状态。

## 5. 领域影响盘点

- 局部策略编排，不新增跨模块实体或结构决策，无需CONTEXT/ADR。

## 6. requirement 回写

- [x] 已backfill `autobn-staged-take-profit.md`为current并更新VISION。

## 7. roadmap 回写

- 非roadmap起头。

## 8. attention.md 候选盘点

- 无通用环境或工作流候选。

## 9. 遗留

- 行情仍按每分钟日K最新close轮询，本feature不处理瞬时触价遗漏。
- 无顺手发现。
