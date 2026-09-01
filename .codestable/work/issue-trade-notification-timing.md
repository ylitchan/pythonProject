---
type: issue
status: completed
---

# 交易通知时序与止盈标记问题

## 目标

修复 `tokenDemo/autoTrade_pm.py` 的两个通知问题：

1. AUTOBN 在重新开仓冷却期内不重复发送分析/交易信号；飞书信号仅在已确认可以开仓、真实下单 API 调用之前发送。
2. 首次部分止盈通知显示“首次止盈”，后续止盈通知显示“止盈”。

范围限定为 `tokenDemo/autoTrade_pm.py` 主链及其对应测试；不改变交易条件、止盈止损轨道、DCA 规则、持仓生命周期或既有渠道边界。

## 现场

- AUTOBN 每分钟由 `rzq_market()` 分批调用 `rzq_token()`；`rzq_token()` 同时负责持仓管理和观察记录开仓。
- 原流程在 `_build_open_signal()` 中完成参数构造后立即发送飞书，之后才在 `rzq_token()` 中检查重新开仓冷却；因此冷却期会出现“已发信号但未真实开仓”。
- `open_bn_position()` 承担余额、标记价格、交易对、止盈止损、价格距离、风险仓位、名义价值、数量、保证金、账户健康度和杠杆等开仓前置校验。
- AUTOA 原本已经在行情请求前执行本地重新开仓冷却检查，本次保留其既有顺序；AUTOBN 对齐为同样的本地状态优先路径。
- `Position` 持有 `tp_count` 与 `close_reason`。首次止盈成功后写回计数；后续止盈分支使用普通“止盈”原因。

## 边界

- 用户已授权完整修复；不得发送真实飞书、PushPlus、企业微信、币安或其他交易所请求，测试全部使用 mock。
- 冷却判断只依赖本地持久化状态，必须早于行情请求、`check_side()`、开仓信号构造和外部通知。
- Observation 超时清理必须排在冷却判断之后：即使观察已过期，只要 `earliest_open_timestamp` 仍在未来，也必须保留记录并跳过本轮开仓分析，不能因先删除记录而绕过冷却。
- 飞书通知位于全部开仓前置校验和杠杆设置成功之后、`new_um_order` 之前；飞书发送失败不得阻断真实下单。
- DCA 复用开仓函数时不传初始 `open_signal`，因此不发送初始分析飞书；成功加仓的既有 PushPlus 行为保持不变。
- 首次/后续止盈只验证和修正通知使用的状态语义，不重写止盈轨道或持仓状态生命周期。

## 证据

### 问题一：根因与修复

- 原因已由只读内存 mock 复现：信号条件满足后 `_build_open_signal()` 发送 1 次飞书，随后冷却检查失败，真实开仓调用为 0。
- `_build_open_signal()` 现只负责构造并返回 `take_profit`、`stop_loss`、`basis_rate` 和消息，不再发送飞书。
- `rzq_token()` 现先读取并构造本地 `Observation`，再执行重新开仓冷却判断；冷却中直接返回，不请求 K 线、不调用 `check_side()`、不构造信号、不发送通知、不下单、不刷新观察记录。
- Observation 超时清理已调整到冷却判断之后，覆盖“观察过期但冷却尚未结束”的边界。
- `open_bn_position()` 现仅在余额、行情、交易对、止盈止损、仓位、名义价值、保证金、健康度及杠杆等前置校验均通过后，在 `new_um_order` 之前发送初始飞书；发送异常单独捕获并记录，不阻断下单。
- 初始开仓成功后的 PushPlus 保留；DCA 不传 `open_signal`，不会误发初始分析飞书。

### 问题二：止盈通知

- 首次分支仍要求 `tp_count < 1`，成功后递增并写回持仓状态；后续分支先递增计数并设置 `close_reason = "止盈"`。
- 新增两轮状态链验证：第一次通知正文包含“平仓依据：首次止盈”，成功写回后第二次达到新的止盈线，通知正文包含“平仓依据：止盈”且不再包含“首次止盈”。
- 该两轮 mock 证据未发现需要重写生产止盈分支。若线上仍显示错误，剩余方向是实际进程版本、状态写回失败、并发覆盖或重复/旧进程，不属于当前代码路径已复现的错误。

### 审查

- 同一 reviewer lineage 已完成复审。
- 首轮 finding `tokenDemo/autoTrade_pm.py:1987-1998` 已 resolved：冷却判断先于 Observation 超时删除。
- 复审完整当前候选及修复增量，未发现新的 blocking/important finding。

## 验收

- 冷却期回归测试覆盖：不请求行情、不下单、不发通知且保留观察及冷却字段。
- 冷却优先于观察过期回归测试覆盖：过期观察在冷却未结束时不被删除、不丢失 `earliest_open_timestamp`。
- BZ/BD/[BZ, BD] 观察有效期测试覆盖策略差异；新的 BD 观察可覆盖旧 BZ 观察并保留冷却字段。
- 初始开仓时序测试确认：前置校验 → 杠杆 → 飞书 → 真实订单 → 成功开仓 PushPlus。
- 前置校验失败时不发送初始飞书；飞书发送失败时仍真实下单并发送成功开仓 PushPlus；DCA 不发送初始飞书。
- 两轮止盈通知测试确认首次/后续文案分别为“首次止盈”/“止盈”。
- 定向模块测试：

  ```text
  uv run python -m unittest tokenDemo.test_autoTrade_pm
  Ran 140 tests
  OK
  ```

- 完整 `tokenDemo` 测试套件（增加最新边界测试后）：

  ```text
  uv run python -m unittest discover -s tokenDemo -p "test_*.py"
  Ran 153 tests
  OK
  ```

- 静态检查通过：

  ```text
  uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py tokenDemo/pushplus_notifications.py tokenDemo/test_pushplus_notifications.py tokenDemo/test_env_credentials.py
  All checks passed!
  ```

- 相关差异 `git diff --check` 通过。
- 测试中的“文件被占用”错误日志来自既有的 `CloseRecordManager` 错误恢复测试；该测试预期写入失败并通过，不是本 issue 的失败。

## 状态与未决

状态：completed。

已完成：冷却前置、冷却与超时优先级修复、信号构造与通知发送职责分离、开仓前置校验后的飞书时序、飞书失败隔离、DCA 通知边界、首次/后续止盈通知回归验证，以及完整测试和复审。

遗留风险：当前无法仅凭本地测试证明线上运行进程已加载最新代码，也无法排除线上持久化写回失败、并发覆盖或重复进程。如果线上第二次止盈仍显示“首次止盈”，应沿这些运行态方向核验，不应在没有新证据时改变止盈轨道。

副作用处理：`tokenDemo/close_records.xlsx` 在任务开始前已有用户运行数据及未提交修改；核查发现当前文件包含既有记录和运行时新增记录，无法安全归因于测试。未执行 `git checkout`、`git reset`、删除或覆盖，保留现有内容。

未提交、未 push。除本 issue 工作游标外，工作树中原有的删除和其他用户变更均未批量恢复。
