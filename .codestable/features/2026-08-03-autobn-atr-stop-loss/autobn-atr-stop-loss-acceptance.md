# AUTOBN ATR 止损距离拆分验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-08-03
> 关联方案 doc：`.codestable/features/2026-08-03-autobn-atr-stop-loss/autobn-atr-stop-loss-design.md`

## 1. 接口契约核对

- [x] AUTOBN 以独立 `TAKE_PROFIT_ATR_FACTOR = 3.0` 和 `STOP_LOSS_ATR_FACTOR = 1.0` 表达价格线职责。
- [x] 基准价100、ATR2时，多头返回 `(106, 98)`，空头返回 `(94, 102)`。
- [x] ATR非正时继续返回 `(0, 0)`。
- [x] 主流程图中的多空职责映射均已落入动态轨道计算。

## 2. 行为与决策核对

- [x] 首次信号、缺失价格线初始化和部分平仓后重算继续复用统一计算入口。
- [x] 多头动态轨道为上侧3 ATR止盈轨、下侧1 ATR止损轨；空头为下侧3 ATR止盈轨、上侧1 ATR止损轨。
- [x] 风险仓位公式未改，但首次开仓自然接收较近的绝对止损价。
- [x] DCA阈值及专用止盈、追踪止损、ATR算法、OI退出未改。
- [x] AUTOA自身的 `SUPERTREND_FACTOR`、初始价格线及动态轨道未改。
- [x] 挂载点反向核对：两个AUTOBN职责常量、统一价格线计算、动态轨道映射和测试均在方案清单内。
- [x] 拔除沙盘：恢复AUTOBN统一3 ATR常量及上下轨、删除职责常量和对应测试即可，无状态迁移残留。

## 3. 验收场景核对

- [x] **S1**：多空固定输入分别生成3 ATR止盈和1 ATR止损。证据：新增直接数值测试。
- [x] **S2**：非正ATR保持零价格线。证据：0与负数边界断言。
- [x] **S3**：首次信号继续调用统一计算入口并把结果传给风险仓位流程。证据：既有开仓表征测试及调用链审查。
- [x] **S4**：价格线缺失时按统一入口初始化。证据：既有ATR初始化测试。
- [x] **S5**：部分平仓剩仓按统一入口重算。证据：既有部分平仓重算测试。
- [x] **S6**：多空动态轨道按职责映射。证据：新增 `_manage_position` 参数断言。
- [x] **S7**：已有非零价格线不自动重算。证据：初始化条件及既有持仓管理测试。
- [x] **S8**：AUTOA及范围外规则保持不变。证据：目标diff审查及全量120测试通过。

验证记录：

- `uv run python -m unittest tokenDemo.test_autoTrade_pm.AutoBNCharacterizationTest -q` → 58 tests / OK。
- `uv run python -m unittest tokenDemo.test_autoTrade_pm -q` → 120 tests / OK。
- `uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py` → All checks passed。
- 日志中的“文件被占用”是既有模拟失败重试场景，最终结果为OK。

## 4. 术语一致性

- `TAKE_PROFIT_ATR_FACTOR` 与 `STOP_LOSS_ATR_FACTOR` 在AUTOBN中分别表达止盈、止损职责。
- 动态轨道仍通过既有管理函数参数传递，没有新增持仓字段或平行状态。
- AUTOA的同名独立类常量未被替换。

## 5. 领域影响盘点

- 新增的是AUTOBN局部风控参数，不新增跨模块实体或对外契约，无需补CONTEXT术语。
- 按方向映射止盈/止损轨是局部、易回退的策略行为，不满足ADR的结构性决策判据。
- 不产生新的全项目流程约束，无需ADR。

## 6. requirement 回写

- [x] 已backfill `.codestable/requirements/autobn-directional-atr-price-control.md`，状态为 `current`。
- [x] 已更新 `.codestable/requirements/VISION.md` Current索引。
- [x] 方案frontmatter已关联 `autobn-directional-atr-price-control`。

## 7. roadmap 回写

- 非roadmap起头，方案无 `roadmap` / `roadmap_item`，无需回写。

## 8. attention.md 候选盘点

- 本feature未暴露下一个feature会重复踩到的环境、命令或工作流陷阱，无attention.md候选。

## 9. 遗留

- 已知限制：已有持仓的非零价格线不迁移；只有进入既有重算路径时才使用新职责倍数。
- 后续优化点：AUTOA仍将自身轨道和初始价格线绑定在统一3 ATR参数，本次按用户范围明确不改。
- 实现阶段顺手发现：无。
