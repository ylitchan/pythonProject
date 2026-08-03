# AUTOA ATR 止盈止损职责拆分验收报告

> 阶段：阶段3（验收闭环）
> 验收日期：2026-08-03
> 关联方案 doc：`.codestable/features/2026-08-03-autoa-atr-stop-loss/autoa-atr-stop-loss-design.md`

## 1. 接口契约核对

- [x] AUTOA新增独立止盈3.0和止损1.0职责常量。
- [x] 基准价100、ATR2时初始止盈106、止损98。
- [x] 持仓仍保存绝对价格，不新增字段。

## 2. 行为与决策核对

- [x] 初始价格线上侧使用3 ATR、下侧使用1 ATR。
- [x] 动态上轨使用3 ATR、动态下轨使用1 ATR。
- [x] DCA、成交量退出、盈利追踪、止盈衰减、ATR算法均未改。
- [x] AUTOBN代码未改。
- [x] 挂载点反向核对及拔除沙盘通过：恢复统一3 ATR常量和两处计算即可卸载。

## 3. 验收场景核对

- [x] **S1**：初始价格线为3 ATR止盈和1 ATR止损。证据：开仓测试新增绝对值断言。
- [x] **S2**：动态轨道上3 ATR、下1 ATR。证据：动态止损轨测试断言止损收紧至1 ATR位置。
- [x] **S3**：已有持仓不自动初始化重算。证据：仅既有动态管理规则可改变持仓价格线。
- [x] **S4**：范围外行为不变。证据：目标diff审查及全量121测试通过。

验证记录：

- AUTOA相关测试：15 tests / OK。
- 全量测试：121 tests / OK。
- Ruff：All checks passed。
- 日志中的“文件被占用”是既有模拟重试场景，最终测试结果为OK。

## 4. 术语一致性

- `TAKE_PROFIT_ATR_FACTOR`与`STOP_LOSS_ATR_FACTOR`和AUTOBN采用相同职责命名，但各属于独立类常量。
- AUTOA旧统一`SUPERTREND_FACTOR`已无引用并删除。

## 5. 领域影响盘点

- 局部风控参数不新增跨模块实体，无需CONTEXT或ADR。

## 6. requirement 回写

- [x] 已backfill `autoa-directional-atr-price-control.md` 为current。
- [x] 已更新VISION Current索引并关联方案。

## 7. roadmap 回写

- 非roadmap起头，无需回写。

## 8. attention.md 候选盘点

- 无项目通用环境或流程候选。

## 9. 遗留

- 已有持仓不做数据迁移，继续由既有动态管理规则推进。
- 无顺手发现。
