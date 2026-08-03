# AUTOA 早期盈利全平验收报告

> 阶段：阶段3（验收闭环）
> 验收日期：2026-08-03
> 关联方案：`.codestable/features/2026-08-03-autoa-early-take-profit/autoa-early-take-profit-design.md`

## 1. 接口契约核对

- [x] 未新增持仓字段，复用`Position.close_reason`。
- [x] 早期盈利全平原因使用与AUTOBN一致的“首次止盈”。
- [x] 阈值为当前止盈距离1/3、1 ATR和入场价5%的最小值。

## 2. 行为与决策核对

- [x] 早期阈值触发后进入既有全平流程，平仓比例100%。
- [x] 价格止盈、价格止损和成交量止损保持优先且互斥。
- [x] 原仅提高止损的早期盈利职责已移除。
- [x] DCA、ATR价格线、成交量止损、行情源和轮询频率未改。
- [x] 挂载点反向核对与拔除沙盘通过。

## 3. 验收场景核对

- [x] 入场10、止盈13、ATR 2、当前价10.5时达到5%阈值并全平。
- [x] 全平数量为全部100股，记录`close_ratio=1.0`。
- [x] 通知与平仓记录均写入“首次止盈”。
- [x] 全平后写入既有观察冷却时间。
- [x] 低于阈值继续既有动态管理。

验证：AUTOA持仓相关12 tests / OK；全量125 tests / OK；Ruff通过。日志中的文件占用异常为既有模拟重试场景，最终结果OK。

## 4. 术语一致性

- “首次止盈”与AUTOBN一致，无新增平行术语。

## 5. 领域影响盘点

- 复用局部退出语义，不新增跨模块实体、结构决策或流程协议，无需CONTEXT/ADR。

## 6. requirement 回写

- [x] 已backfill `autoa-early-take-profit.md`为current并更新VISION。

## 7. roadmap 回写

- 非roadmap起头。

## 8. attention.md 候选盘点

- 无通用环境或工作流候选。

## 9. 遗留

- 无。
