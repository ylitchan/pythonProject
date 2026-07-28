---
doc_type: refactor-apply-notes
refactor: 2026-07-28-autotrade-pm-redundancy-cleanup
---

# autotrade-pm-redundancy-cleanup apply notes

## 步骤 1：清理死配置、死常量与不可达分支

- 完成时间：2026-07-28
- 改动文件：`tokenDemo/autoTrade_pm.py`
- 完成内容：删除 `margin_mode` / `position_mode` 解析、`slot_balance`、个人微信 `wx` 链路、五枚失联旧常量、`get_symbols_info` 无参兜底、AUTOBN/AUTOA 切比雪夫 `message` 返回字段。
- 验证结果：旧符号 grep 零残留；117 个测试通过；Ruff 通过。
- 偏离：用户确认 AUTOA 切比雪夫同形冗余一并清理，范围由原 17 条扩为 20 条候选。

## 步骤 2：接线 BD 独立窗口常量

- 完成时间：2026-07-28
- 改动文件：`tokenDemo/autoTrade_pm.py`、`tokenDemo/test_autoTrade_pm.py`
- 完成内容：新增 `BD_VOLUME_LOOKBACK_COUNT/RECENT_COUNT` 与 `BD_OI_LOOKBACK_COUNT/RECENT_COUNT`，默认值保持 10/3；OI 最小长度复用 `OI_QUERY_LIMIT`；删除 `_is_bd_observation` 中由 `rzq_token` 的 `KLINE_LIMIT` 入口守卫已保证的 K 线长度重复判断。
- 验证结果：新增常量关系测试；默认切片与原 `[-10:-3]` / `[-3:]` 等价；117 个测试通过。
- 偏离：原设计只删不接线；用户明确要求 BD 窗口可配置，且确认 BZ/BD 共用入口 K 线长度守卫后改为独立接线。

## 步骤 3：收紧两套通知签名

- 完成时间：2026-07-28
- 改动文件：`tokenDemo/autoTrade_pm.py`
- 完成内容：AUTOBN `send_msg.qy_key` 与 AUTOA `send_msg.pushplus_notification` 改为仅关键字参数；AUTOA 两个位置实参调用改为显式关键字。
- 验证结果：调用点枚举确认兼容；117 个测试通过。
- 偏离：AUTOA 同形隐患由用户要求一并处理。

## 步骤 4：清理恒真恒假条件与重复计算

- 完成时间：2026-07-28
- 改动文件：`tokenDemo/autoTrade_pm.py`
- 完成内容：DCA 失败回滚无条件 `pop()`；SHORT 侧同生同灭 OI 返回值收为单判空；删除 AUTOBN ATR 恒假长度守卫；AUTOA DataFrame 同体分支合并；AUTOA ATR 复用 `highs[-1]` / `lows[-1]`；`_manage_position` 的 `hl2` 单次计算。
- 验证结果：117 个测试通过；Ruff 通过。
- 偏离：无。

## 步骤 5：收拢开平仓公共逻辑

- 完成时间：2026-07-28
- 改动文件：`tokenDemo/autoTrade_pm.py`
- 完成内容：抽 `_clear_closed_position` 收拢三处平仓清理；抽 `_build_open_signal` 收拢多空开仓信号；止盈止损统一命名为 `take_profit/stop_loss`，通知与下单复用同一组值；删除 `should_open` 后的死兜底、二次计算与死早退。
- 验证结果：117 个测试通过；既有平仓三路径与多空开仓用例全绿。
- 偏离：无。

## 步骤 6：清理 AUTOA 数据与平仓原因冗余

- 完成时间：2026-07-28
- 改动文件：`tokenDemo/autoTrade_pm.py`
- 完成内容：`tot_v` 纳入新浪分时接口必需字段，允许值为空并保留 `v.sum()` 回退；删除第二次 `pd.DataFrame(res)`；删除平仓原因最后一个不可达 `elif`。
- 验证结果：实时核查 `sh600000/sz000001/sh601318/sz300750`：每行均有 `tot_v` 字段，15:00 后附加行值可为空，15:00 非空累计值与同期 `v` 累加精确相等；117 个测试通过。
- 偏离：用户要求先查实接口契约；确认后选择单 DataFrame、保留现有成交量口径。

## 步骤 7：补刻画测试并全量验证

- 完成时间：2026-07-28
- 改动文件：`tokenDemo/test_autoTrade_pm.py`
- 验证结果：
  - `uv run python -m unittest tokenDemo.test_autoTrade_pm -q` → **Ran 117 tests / OK**（原 114 + 新增 3 个测试方法，子测试覆盖 AUTOBN/AUTOA 的单元素、零标准差、k≤1、k>1）
  - `uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py` → **All checks passed**
  - checklist：`validate-yaml.py --file ...` → **1 passed / 0 failed**（PyYAML 未安装，工具使用内置 fallback parser 并给出 warning）
- 偏离：测试运行中出现 `OSError: 文件被占用` 日志，这是 `CloseRecordManager` 的既有模拟失败场景，用例预期覆盖并最终 OK，不是测试失败。
