---
type: feat
status: completed
---

# 渠道区分改造

## 目标

调整 `tokenDemo/autoTrade_pm.py` 的消息路由，不改变 AUTOA 当前 BZ 可直接开仓的交易行为：

- AUTOA 只有 BZ 的信号发送企业微信；企业微信仅服务 AUTOA 信号。
- AUTOA 含 `N` 的初始开仓、DCA 加仓、成功平仓和每日持仓发送 PushPlus。
- AUTOA 普通筛选/分析和非交易异常不发送外部渠道；内部观察、持仓状态和交易所实际交易链路仍保留。
- AUTOBN 的成功开仓（包括 DCA）、成功平仓和既有每日持仓摘要发送 PushPlus。
- 飞书仅发送 AUTOBN 的分析/开仓前信号；不发送 AUTOA 消息、AUTOBN 实际成交结果、每日持仓或普通异常。
- 同一条 AUTOBN 分析信号只发送一次飞书，消除当前双重 `send_msg()` 调用造成的重复。
- PushPlus 是消息渠道；通知标题和 Markdown 正文作为消息对象传入，不再单独传 `pushplus_notification` 参数。

## 现场

已核实：

- AUTOA `send_msg()` 和 AUTOBN `send_msg()` 均采用单一 `channel` 参数；PushPlus 以 `TradeNotification` 消息对象作为 `msg`、并传 `channel="pushplus"`，不再有独立 `pushplus_notification` 参数。
- AUTOA 只有 BZ 的初始信号发送企业微信；含 N 的初始开仓、DCA 加仓、成功平仓和每日持仓发送 PushPlus；普通分析/筛选消息不对外发送。
- AUTOA 每日持仓原有消息生成逻辑保留，仅包装为 PushPlus 通知；空仓也发送每日持仓。
- AUTOA 平仓后当前仍调用 `CloseRecordManager.record_close_async()`；本次“不再记录”解释为不再发送外部渠道，不删除内部状态或 Excel 平仓记录。
- AUTOBN `send_msg()` 当前按显式渠道路由：成功交易和每日持仓发送 PushPlus，分析信号发送飞书，普通异常不发送外部渠道。
- AUTOBN `_build_open_signal()` 当前只调用一次 `send_msg()`，避免分析信号重复发送。
- AUTOBN 早间余额和持仓摘要原本已生成，本次仅将原消息改由 PushPlus 发送。
- AUTOA 当前链路是“涨停池 → 观察记录 → BZ 条件满足并直接开仓”，N 只在已有 BZ 且满足跳空条件时追加；本次保持该交易行为。

## 边界

### 已确认

- “不带 N 不再发送、不再记录”指不发送 AUTOA 的分析/筛选消息，不指内部状态、日志或 `close_records.xlsx` 删除。
- AUTOA 只有 BZ 的初始信号发送企业微信；含 N 的初始开仓、DCA 加仓、成功平仓和每日持仓只发送 PushPlus。
- AUTOBN 成功开仓（包括 DCA）、成功平仓和既有每日持仓摘要发送 PushPlus；分析信号只发送飞书；失败/跳过不纳入成功交易 PushPlus 路由。
- PushPlus 的通知对象通过 `msg` 传入，渠道统一由 `channel` 选择；不保留 `pushplus_notification` 并列参数。
- 本次不把 BZ 改造成只入池、不直接开仓的严格三阶段策略。

### 待实现细节

- 使用显式事件类型/参数控制 `send_msg()` 的目标渠道，避免普通通知方法广播所有渠道。
- AUTOA 每日持仓直接包装为 PushPlus 通知；空仓也要发送每日持仓。
- AUTOBN 每日余额和持仓摘要直接包装为 PushPlus 通知。
- AUTOA 分析/筛选、非交易异常仅写日志；只有 BZ 的初始信号发送企业微信；含 N 的初始开仓、DCA 加仓、成功平仓和每日持仓发送 PushPlus。
- AUTOBN 信号仅发送飞书；AUTOBN 实际成功开平仓（含 DCA 开仓）和既有每日持仓仅发送 PushPlus。
- 由于 AUTOBN 开仓/平仓失败和跳过不属于成功交易事件，本次不发送 PushPlus。

## 必须修改

- `tokenDemo/autoTrade_pm.py`
  - 明确 AUTOA/AUTOBN 的消息渠道参数或专用事件入口。
  - 移除 AUTOBN 信号的双重发送路径。
  - 为 AUTOA/AUTOBN 每日持仓构造 PushPlus 通知。
  - 将 AUTOA 含 N 的初始开仓、DCA 加仓、成功平仓和每日持仓限定到 PushPlus；保留只有 BZ 的初始信号企业微信路径。
  - 保留成功开平仓和每日持仓的 PushPlus。
  - 禁止 AUTOA 普通消息和 AUTOBN 普通消息进入错误渠道。

## 需要验证

- AUTOA 只有 BZ 的初始信号：仅企业微信一次；不发 PushPlus 或飞书。
- AUTOA 含 N 的初始开仓、DCA 加仓和成功平仓：仅 PushPlus 一次；不发企业微信或飞书。
- AUTOA 成功平仓：仅 PushPlus；不发企业微信或飞书；内部平仓记录仍执行。
- AUTOA 分析/筛选和非交易异常：不发外部渠道；内部交易状态和平仓记录保持。
- AUTOA 每日持仓（有仓/空仓）：PushPlus 各发送一次，原始消息内容保持不变。
- AUTOBN 分析信号：飞书仅一次，不发企微/PushPlus。
- AUTOBN 成功开仓/平仓：PushPlus各发送一次，不发飞书/企微。
- AUTOBN 每日持仓：沿用原有余额和持仓消息内容，改为 PushPlus 发送一次，不发飞书/企业微信。
- AUTOBN DCA 成功开仓：按成功开仓事件发送 PushPlus 一次，不发飞书/企业微信。
- 失败/跳过消息：不进入本次成功交易 PushPlus 路由。
- PushPlus、飞书发送失败不阻断交易主流程。
- 现有测试套件保持通过，且不产生真实外部请求。

## 证据

- AUTOA 观察确认与开仓：`tokenDemo/autoTrade_pm.py:3226-3352`
- AUTOA 平仓与内部记录：`tokenDemo/autoTrade_pm.py:3027-3223`
- AUTOA 每日持仓：`tokenDemo/autoTrade_pm.py:2779-2832`
- AUTOA 通知入口：`tokenDemo/autoTrade_pm.py:2653-2693`
- AUTOBN 通知入口：`tokenDemo/autoTrade_pm.py:570-628`
- AUTOBN 信号构造：`tokenDemo/autoTrade_pm.py:1930-1966`
- AUTOBN 早间持仓：`tokenDemo/autoTrade_pm.py:2339-2365`
- PushPlus格式化器：`tokenDemo/pushplus_notifications.py:18-77`
- 路由测试：`tokenDemo/test_autoTrade_pm.py:769-814`、`tokenDemo/test_autoTrade_pm.py:2631-2660`
- 每日持仓通知测试：`tokenDemo/test_autoTrade_pm.py:432-491`、`tokenDemo/test_pushplus_notifications.py:36-43`

## 验收

完成代码和定向测试后，工作游标状态改为 `completed`；若发现边界改变，先更新本游标再修改实现。不得发送真实 webhook 或 PushPlus 请求，不提交或推送 Git。

- `uv run python -m unittest tokenDemo.test_pushplus_notifications tokenDemo.test_autoTrade_pm tokenDemo.test_env_credentials`：146 tests，OK。
- `uv run python -m unittest discover -s tokenDemo -p "test_*.py"`：146 tests，OK；覆盖 `test_backtest_autoa_parity.py` 的模型等价性验证。
- `uv run python -m unittest discover`：未发现测试（项目测试位于 `tokenDemo/`，退出码 5），不作为验收依据。
- 测试均使用 mock，不执行真实 webhook 或 PushPlus 请求。

## 状态与未决

状态：completed，生产代码和测试已按当前渠道边界调整，定向与完整 tokenDemo 测试均已通过。

未决：无。本次不提交、不 push。
