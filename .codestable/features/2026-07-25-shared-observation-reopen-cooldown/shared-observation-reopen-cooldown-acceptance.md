# shared-observation-reopen-cooldown 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-07-25
> 关联方案：`.codestable/features/2026-07-25-shared-observation-reopen-cooldown/shared-observation-reopen-cooldown-design.md`

## 1. 接口契约核对

- [x] 共用 `Observation` 新增 `earliest_open_timestamp: Optional[float] = None`，并提供严格小于边界的冷却判断。
- [x] 旧 JSON 缺字段恢复为 `None`，数值经 `model_dump` / `model_validate` 保持不变。
- [x] AUTOBN 已停止初始化、写入和读取 `CLOSE_TS`，冷却只来自 Observation。
- [x] AUTOA 使用新浪实际交易日历取得平仓日后的第二个后续交易日，不用自然日近似。

## 2. 行为与决策核对

- [x] AUTOBN 在确认交易所仓位为零的所有清仓路径写入当前时间加24小时；部分平仓不写。
- [x] AUTOA 在完整平仓状态转换中先确定冷却日期并更新已有Observation，再移除Position。
- [x] AUTOA日历无法提供两个后续交易日时保留仓位，不退化为48小时或工作日。
- [x] 当前时间等于最早开仓时间时冷却结束。
- [x] 未补造Observation、未修改Observation删除逻辑，其他策略门槛保持不变。

## 3. 验收场景核对

- [x] **默认与兼容**：新实例和旧JSON均为`None`；数值状态可持久化恢复。证据：`ObservationTest`。
- [x] **边界**：最早时间前仍冷却，恰好边界解除。证据：`test_reopen_cooldown_uses_strict_timestamp_boundary`。
- [x] **AUTOBN写入**：确认仓位为零时写入`close_time + 24h`并清除本地Position。证据：`test_zero_exchange_position_writes_24_hour_cooldown`。
- [x] **AUTOA T+2**：7月22日平仓时最早日期为7月24日。证据：`test_reopen_timestamp_is_second_following_trading_day`、`test_close_writes_second_following_trading_day_cooldown`。
- [x] **周末和休市**：交易日历从9月30日后跳过国庆休市及周末，返回10月9日、10月12日。证据：`test_following_trading_days_skip_weekend_and_market_holiday`。
- [x] **提前退出**：冷却中的AUTOA不加载行情。证据：`test_cooldown_returns_before_loading_market_data`。
- [x] **回归**：`uv run python -m unittest tokenDemo.test_autoTrade_pm`运行66项，结果`OK`；模拟文件占用堆栈是既有错误路径测试。
- [x] **静态检查**：`uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py`通过。

## 4. 领域影响与回写

- [x] 新建`.codestable/requirements/shared-observation-reopen-cooldown.md`，状态为`current`。
- [x] 已更新`.codestable/requirements/VISION.md` Current索引。
- [x] 无新模块边界、依赖或跨系统接口，不需要ADR。
- [x] 无可复用的环境或工具陷阱，不新增attention条目。

## 5. 遗留

- `autoTrade.py`与`autoTrade_papi.py`是其他实现，仍各自含`CLOSE_TS`；本feature只覆盖用户指定且当前测试维护的`autoTrade_pm.py`，未越界同步修改。
- 未提交或推送；版本控制动作等待用户明确授权。
