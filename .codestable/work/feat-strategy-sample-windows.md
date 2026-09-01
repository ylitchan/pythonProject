---
type: feat
status: completed
---

# AUTOA/AUTOBN 策略样本周期调整

## 目标

调整 `tokenDemo/autoTrade_pm.py` 中两处策略样本窗口：

- AUTOA 日线成交量只获取 20 根，排除最近 5 根后，以前 15 根作为切比雪夫样本；最近成交量门槛使用后 5 根。
- AUTOBN 的 BZ 做多从观察池决定开仓时，将历史 OI 和历史多空比从 `1d` 改为 `1h`；查询 30 根，排除最近 6 根，以前 24 根作为切比雪夫样本。
- AUTOBN 按现有结构等价迁移：当前 5m OI、当前 5m 多空比、blend 增量权重、完整历史序列最大值门槛和 5m OI 回撤保护逻辑保持不变。
- ATR 参数周期按一周调整：AUTOBN 为 7 根日 K，AUTOA 为 5 根 A 股交易日 K；ATR 算法、上限、倍数及其下游止盈止损/DCA公式保持不变。

## 现场

- AUTOA 当前通过日 K 成交量窗口判断 BZ，常量为 `VOLUME_CHEB_SAMPLE_START_OFFSET = -30`、`VOLUME_CHEB_SAMPLE_END_OFFSET = -10`、`VOLUME_CHEB_REQUIRED_HISTORY = 30`。
- AUTOA 当前切比雪夫样本和近期最大成交量门槛都由上述偏移量控制；`test_backtest_autoa_parity.py` 另有 `[-30:-10]` 的等价模型硬编码。
- AUTOBN 当前 BZ 做多在 `check_side(LONG)` 中读取 30 根 `1d` OI、30 根 `1d` 多空比，并读取当前一根 5m OI 和当前一根 5m 多空比。
- AUTOBN 当前从完整 30 根日 OI 中排除最近 10 根，以前 20 根计算切比雪夫；blend 使用该历史窗口末根 OI 及同时间戳的多仓比例作为基准。
- `_get_oi_1d_data()` 同时需要服务 BD 的 `1d` 和 BZ 做多的 `1h`，适合参数化周期并隔离缓存；历史多空比只有 BZ 做多消费，迁移到 `1h` 后不再需要 `1d` 缓存。
- AUTOBN 的日 K 仍服务于 BZ/BD 入池、观察池价格方向、ATR、止盈止损和持仓管理，不属于本次周期迁移范围。

## 边界

### 已确认

- AUTOA 获取数量由 30 根日 K 改为 20 根，不是继续获取 30 根后截取 20 根。
- AUTOA 排除最近 5 根日 K；切比雪夫样本为 `[-20:-5]`，共 15 根，代表约一个月数据中扣除最近一周。
- AUTOA 当前成交量与近期最大值比较使用最近 5 根，即与切比雪夫样本的排除区间一致。
- AUTOBN BZ 做多历史 OI 和历史多空比改用 `1h`；获取 30 根、排除最近 6 根，切比雪夫样本为前 24 根。
- AUTOBN `window_end` 改为这 24 根小时样本的最后一根，即完整 30 根中的倒数第 7 根；多仓比例仍按相同时间戳配对。
- AUTOBN 当前 5m OI、当前 5m 多空比和 `OI_DELTA_LONG_RATIO_WEIGHT = 0.4` 保持不变。
- AUTOBN 的 `oi_5m_last >= max(history_oi)` 按原结构等价迁移，仍与完整 30 根历史 OI 的最大值比较，而不是只与前 24 根切比雪夫样本比较。
- AUTOBN BD 做空继续使用 `1d` OI；AUTOA 与 AUTOBN 的日 K 交易条件均不改为小时 K。
- 历史 OI 取数逻辑应参数化复用，不复制一套仅周期不同的实现；OI 缓存必须按 symbol 与 period 隔离，UTC 可用边界必须按周期计算。
- 历史多空比仅由 BZ 做多使用，直接改成 `1h` 专用读取与缓存，不保留无消费者的 `1d` 多空比缓存。
- AUTOBN/AUTOA 的 ATR 数据周期仍为日 K，只将样本根数分别从 10 改为 7/5。
- AUTOA 回测模型的 ATR 周期和盘中末根 TR 替换窗口必须同步，保持实盘/回测等价。

### 非目标

- 不改变 BZ/BD 入池条件、阴阳线或价格方向判断、ATR 算法、止盈止损/DCA公式、仓位管理、通知渠道和下单时序。
- 不改变 AUTOBN 的 BD 做空历史周期与窗口。
- 不把当前 5m 单根 OI/多空比读取强行并入历史序列通用方法。
- 不提交、不 push，不发送真实通知或交易所请求。

## 证据

- AUTOBN 历史 OI 与缓存：`tokenDemo/autoTrade_pm.py:1040-1071`
- AUTOBN BZ/BD OI 窗口：`tokenDemo/autoTrade_pm.py:1073-1088`
- AUTOBN 做多 blend 与切比雪夫判断：`tokenDemo/autoTrade_pm.py:1090-1189`
- AUTOBN 历史多空比与缓存：`tokenDemo/autoTrade_pm.py:1229-1262`
- AUTOBN 日 K、观察池开仓与入池链路：`tokenDemo/autoTrade_pm.py:1968-2192`
- AUTOA 样本窗口常量：`tokenDemo/autoTrade_pm.py:2463-2468`
- AUTOA 日 K取数及成交量判断：`tokenDemo/autoTrade_pm.py:3079-3085`、`tokenDemo/autoTrade_pm.py:3291-3323`
- AUTOA 等价模型硬编码：`tokenDemo/test_backtest_autoa_parity.py:49-57`
- AUTOBN 缓存与 blend 相关测试：`tokenDemo/test_autoTrade_pm.py:2063-2380`、`tokenDemo/test_autoTrade_pm.py:2518-2638`、`tokenDemo/test_autoTrade_pm.py:2741-2953`

## 必须修改

- `tokenDemo/autoTrade_pm.py`
  - AUTOA 日 K请求与最低历史数量改为 20 根，样本窗口改为 `[-20:-5]`，近期门槛改为最近 5 根。
  - 将 AUTOBN 历史 OI 读取抽象为支持 `1d`/`1h` 周期的通用实现。
  - 让历史 OI 缓存按周期隔离，并正确计算 UTC 日边界和 UTC 小时边界。
  - 将历史多空比读取及缓存由 `1d` 改为 BZ 做多专用的 `1h`。
  - AUTOBN BZ 做多改用 30 根 `1h` OI/多空比，并将排除数改为 6。
  - AUTOBN BD 做空继续显式使用 `1d` OI。
  - AUTOBN/AUTOA 的 `ATR_PERIOD` 分别改为 7/5；不改 ATR 计算方式、风控倍数和调用位置。
- `tokenDemo/test_autoTrade_pm.py`
  - 更新/补充 1d/1h OI 缓存隔离、各自时间边界、API 周期参数和失败回退测试。
  - 更新历史多空比的 1h 时间边界、API 周期参数、缓存和失败回退测试，并确认不再保留 1d 消费路径。
  - 更新 blend、时间戳配对、切比雪夫样本、完整 30 根最大值门槛及 BD 保持 1d 的测试。
  - 更新 AUTOA 20 根日 K和 `[-20:-5]` 窗口边界测试。
  - 增加 AUTOBN/AUTOA ATR 周期分别为 7/5 的回归断言。
- `tokenDemo/test_backtest_autoa_parity.py`
  - 将等价模型同步为 20 根日 K、`[-20:-5]` 样本及最近 5 根门槛。
- `tokenDemo/backtest_autoa.py`
  - 将 AUTOA 回测模型的历史行数、成交量样本长度/滞后和近期最大值窗口同步为 20、15/5 和 5，保持与实盘模型等价。
  - 将回测 ATR 周期及依赖该周期的滚动 TR 窗口同步为 5。

## 需要验证

- AUTOA 只请求/要求 20 根日 K；少于 20 根时不进入策略判断。
- AUTOA 切比雪夫输入恰为前 15 根，当前成交量与最近 5 根最大值比较。
- AUTOA 生产模型与回测等价模型保持一致。
- AUTOBN BZ 做多向 OI 和多空比 API 请求 `period="1h"`、`limit=30`。
- AUTOBN BZ 做多切比雪夫输入恰为前 24 根小时 OI，`window_end` 为倒数第 7 根，并与同时间戳 1h 多仓比例配对。
- AUTOBN blend 仍使用当前 5m OI和固定权重 0.4，仍与当前 5m 多仓比例比较。
- AUTOBN 历史峰值门槛仍覆盖完整 30 根小时 OI。
- AUTOBN BD 入池、刷新和做空扣扳机继续使用 `1d` OI，行为不因做多周期迁移而改变。
- 同一 symbol 的 `1d`/`1h` OI 缓存互不覆盖，API 失败分别回退对应周期缓存。
- 历史多空比只维护 `1h` 缓存并供 BZ 做多使用；BD 做空不请求历史或 5m 多空比。
- 所有外部接口使用 mock；运行定向测试及影响范围相称的 `tokenDemo` 回归测试。
- AUTOBN/AUTOA 默认 `ATR_PERIOD` 分别为 7/5；AUTOBN 仍按 Wilder RMA 平滑，AUTOA 仍取周期内 TR 均值，周期不足时仍按既有规则返回 0。
- ATR 周期变化之外，止盈止损倍数、DCA 系数、轨道和触发公式不变。

## 验收

- 先增加或更新能够表达上述窗口、周期、缓存隔离和策略边界的回归测试，再修改实现。
- `tokenDemo.test_autoTrade_pm` 与 `tokenDemo.test_backtest_autoa_parity` 相关测试通过。
- 与影响范围相称的 `tokenDemo` 测试套件通过，静态检查和 `git diff --check` 通过。
- 不产生真实交易所、飞书、PushPlus 或企业微信请求。

实际验收结果：

- 先增加 AUTOBN/AUTOA 默认 ATR 周期测试，旧实现分别因 `10 != 7`、`10 != 5` 按预期失败；实现后定向测试 2 tests，OK。
- `uv run python -m unittest tokenDemo.test_autoTrade_pm`：145 tests，OK。
- `uv run python tokenDemo/test_backtest_autoa_parity.py`：ATR、切比雪夫、BZ 完整条件、N 条件和持仓端 ATR 均为 0 个不一致，输出“全部通过”。
- `uv run python -m unittest discover -s tokenDemo -p "test_*.py"`：158 tests，OK；同时执行等价模型检查并输出“全部通过”。
- `uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py tokenDemo/backtest_autoa.py tokenDemo/test_backtest_autoa_parity.py`：All checks passed。
- 相关文件 `git diff --check` 通过。
- 测试使用 mock，不发送真实交易所订单或外部通知。测试日志中的“文件被占用”来自既有错误恢复测试，属于预期覆盖并通过。

## 状态与未决

状态：completed；样本窗口、历史周期、缓存隔离和 ATR 7/5 周期调整均已实现并验收。

已完成：AUTOA 改为 20 根日 K、排除 5 根；AUTOBN BZ 做多改为 30 根小时数据、排除 6 根，并按原结构等价迁移；历史 OI 按 `symbol + period` 复用并隔离缓存，历史多空比只保留做多所需的 `1h` 缓存；BD 做空继续使用 `1d` OI；AUTOBN/AUTOA 的 ATR 参数周期分别改为 7/5，并同步 AUTOA 回测模型。

副作用处理：`tokenDemo/close_records.xlsx` 在本任务开始前已存在未提交修改，本次没有对其执行恢复、覆盖或删除。

未决：无；未提交、未 push。
