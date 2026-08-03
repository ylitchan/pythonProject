# BZ 多头 OI 回撤平仓验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-07-29
> 关联方案 doc：`.codestable/features/2026-07-29-bz-long-oi-drawdown-exit/bz-long-oi-drawdown-exit-design.md`

## 1. 接口契约核对

- [x] 开仓最新 5m OI 为 120 时，保存的 `stop_guard_threshold` 为 108，符合独立10%回撤线。
- [x] `stop_guard_threshold` 从历史基线均值语义变为本次 BZ 开仓的绝对 OI 平仓线，未新增持仓字段。
- [x] 流程图各节点均有落点：开仓确认生成阈值、持仓轮询 OI、边界比较、全平或继续管理。

## 2. 行为与决策核对

- [x] 新增 `BZ_LONG_OI_DRAWDOWN_RATIO = 0.1`，没有复用或修改 BD 常量。
- [x] 多头 OI 平仓不再请求或判断 LSR；`_get_lsr_5m_data` 的剩余调用仅属于 BZ 开仓 blend。
- [x] OI 平仓仍排在价格止损和止盈检查之后，触发时沿用全平及“OI止损”原因。
- [x] 最新 OI 不可用时 `oi_stop_triggered` 为假，不误平仓。
- [x] 明确未改 BZ 入池、blend、切比雪夫、OI 创新高、ATR、DCA 和 BD 路径。
- [x] 挂载点反向核对：独立常量、开仓阈值生成、持仓 OI 检查和测试四类均与方案一致，无清单外引用。
- [x] 拔除沙盘：恢复阈值来源与 LSR 门槛、删除独立常量及测试即可卸载，无新数据迁移或外部接口残留。

## 3. 验收场景核对

- [x] **S1**：开仓 OI × 90% 写入平仓线。证据：`AutoBNLongSignalTest`，120 → 108。
- [x] **S2**：OI 等于阈值时不依赖 LSR并全平。证据：`AutoBNCharacterizationTest`，100 → 触发“OI止损”。
- [x] **S3**：OI 高于阈值不平仓。证据：101 > 100，用例断言未调用平仓。
- [x] **S4**：OI 不可用不误平仓。证据：既有空数据路径及全量测试。
- [x] **S5**：空头不使用该规则。证据：`is_long` 守卫及既有空头持仓用例。
- [x] **S6**：BZ 入池/开仓确认与 BD 逻辑未变。证据：目标 diff 审查、相关61个测试及全量118个测试通过。
- [x] **S7**：BZ 与 BD 回撤常量独立。证据：两个独立类常量和各自独立引用。

验证记录：

- `uv run python -m unittest tokenDemo.test_autoTrade_pm.AutoBNCharacterizationTest tokenDemo.test_autoTrade_pm.AutoBNLongSignalTest -q` → 61 tests / OK。
- `uv run python -m unittest tokenDemo.test_autoTrade_pm -q` → 118 tests / OK。
- `uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py` → All checks passed。
- 测试日志中的“文件被占用”是既有模拟重试场景，最终测试结果为 OK。

## 4. 术语一致性

- `BZ_LONG_OI_DRAWDOWN_RATIO` 唯一定义、唯一计算引用，明确区分 BD 回撤参数。
- `stop_guard_threshold` 继续沿用现有持仓模型字段，无平行字段或同义新概念。
- “OI止损”继续沿用现有平仓原因，没有新增文案分支。

## 5. 领域影响盘点

- 新增的是既有 BZ 风控能力的行为边界，不新增跨模块领域实体，无需 `cs-domain` 术语补录。
- 独立多空回撤参数是局部、易回退的策略调参选择，不满足 ADR 的结构性决策判据。
- 不产生新的全项目流程约束，无需 ADR。

## 6. requirement 回写

- [x] 已 backfill `.codestable/requirements/autobn-bz-long-oi-drawdown-exit.md`，状态为 `current`。
- [x] 已更新 `.codestable/requirements/VISION.md` Current 索引。
- [x] 方案 frontmatter 已关联 `autobn-bz-long-oi-drawdown-exit`。

## 7. roadmap 回写

- 非 roadmap 起头，方案无 `roadmap` / `roadmap_item`，无需回写。

## 8. attention.md 候选盘点

- 本 feature 未暴露下一个 feature 会重复踩到的环境、命令或工作流陷阱，无 attention.md 候选。

## 9. 遗留

- 已知限制：已有非零 `stop_guard_threshold` 持仓不迁移，继续使用其持久化绝对阈值直至仓位结束；这是方案明确边界。
- 后续优化点：回撤比例是否需要进一步校准，应基于实盘或回测另行立项。
- 实现阶段顺手发现：无。
