---
doc_type: refactor-design
refactor: 2026-07-11-auto-trade-core
status: approved
scope: CloseRecordManager 平仓写入路径与 AUTOBN.rzq_token 持仓分支
summary: 删除同步平仓记录旧入口、按 sheet 聚合批量写入，并以刻画测试保护交易优先级后拆分 AUTOBN 持仓处理职责
---

# auto-trade-core refactor design

## 1. 本次范围

- 执行 scan #1、#2、#3，用户于 2026-07-11 明确整体放行。
- 删除 `CloseRecordManager.record_close()`；生产异步接口及 Excel 文件契约不变。
- 优化 `_record_close_batch()` 的批次内 DataFrame 合并次数。
- 仅拆分 `AUTOBN.rzq_token()` 的持仓分支；保留 observation 开仓分支原位。
- 明确不做：拆分整个 `autoTrade_pm.py`、修改任何交易条件、调整 API 请求实时性、重排止损优先级、变更通知内容、修改 AUTOA 策略。
- 预估风险：整体高；前两步低到中，交易函数拆分高风险但全部由自动化测试自证，不需要账户实测。

## 2. 前置依赖

- 将同步入口的 Excel 契约测试改为直接调用 `_record_close_batch()`，再删除入口。
- 为批量写补同 sheet、跨 sheet、顺序和 concat 次数测试。
- 为持仓分支补齐以下刻画测试：
  - 价格止损/止盈触发时不请求多空比和 OI；
  - OI 与多空比同时满足时保持 OI 止损优先；
  - 任一平仓触发后不进入 DCA 或动态目标更新；
  - LONG/SHORT DCA 成功后的均价与止盈更新；
  - LONG/SHORT DCA 失败时撤销刚追加的 DCA 标签；
  - 未平仓时更新后的 Position 仍写回 `alert_all`。
- 测试只使用 mock，不访问真实账户、不真实下单。

## 3. 执行顺序

### 步骤 1：删除同步平仓记录入口

- 引用方法：M-L2-02 Inline Function
- 具体操作：把原同步测试输入转换为 `_record_close_batch()` 接受的记录；确认生产路径只用 `record_close_async()`；删除 `record_close()`。
- 退出信号：全仓 `CloseRecordManager.record_close(` 零引用，CloseRecordManager 目标测试通过。
- 验证责任：AI 自证。
- 回滚：恢复同步方法和原测试调用。

### 步骤 2：按 sheet 合并批次

- 引用方法：M-L4-02 Batching
- 具体操作：按首次出现顺序建立 `sheet_name -> records` 分组；过滤 `source` 后每个 sheet 一次构造 DataFrame、一次 concat；原有 sheet 读写方式不变。
- 退出信号：相同 sheet 多条记录保持顺序；跨 sheet 正确归类；每个有新增记录的 sheet 只调用一次 concat；其他 sheet 保留；目标测试通过。
- 验证责任：AI 自证。
- 回滚：恢复逐记录 concat 循环。

### 步骤 3：补齐 AUTOBN 持仓分支刻画测试

- 引用方法：M-L1-04 Characterization Test
- 具体操作：只新增测试和测试辅助方法，不改生产逻辑；覆盖退出优先级、API 调用边界、DCA 成败和状态写回。
- 退出信号：新增测试在当前实现上全部通过，证明断言刻画的是现状而非期望改动。
- 验证责任：AI 自证。
- 回滚：删除新增测试。

### 步骤 4：提取持仓退出判断与执行

- 引用方法：M-L2-01 Extract Function、M-L2-05 Decompose Conditional
- 具体操作：将 ATR 初始化、退出触发数据获取及平仓执行提取为 AUTOBN 内部方法；使用明确返回值告知调用方本轮是否已平仓；保持价格判断 → 多空比/OI请求 → OI/多空比 → 初始止损 → 止盈的既有顺序。
- 退出信号：步骤 3 的退出优先级和调用边界测试通过；原止损回归测试通过。
- 验证责任：AI 自证。
- 回滚：内联提取的方法恢复原代码块。

### 步骤 5：提取 LONG/SHORT 持仓管理

- 引用方法：M-L2-01 Extract Function、M-L2-05 Decompose Conditional
- 具体操作：分别提取 LONG 与 SHORT 的 DCA、止盈衰减及追踪止损更新；共享指标仍在原顺序计算后传入，避免重复 API 或指标计算；最终状态仍在原持仓分支末尾统一写回。
- 退出信号：LONG/SHORT DCA、动态目标和状态写回测试通过；目标 AutoBN 测试通过。
- 验证责任：AI 自证。
- 回滚：逐个内联 LONG/SHORT 方法。

### 步骤 6：整体回归与静态核对

- 引用方法：M-L1-04 Characterization Test
- 具体操作：运行 `tokenDemo.test_autoTrade_pm` 全部测试、Python 编译检查、`git diff --check`；审查 diff 确认无交易常量、条件比较符、消息文本和外部 API 参数变化。
- 退出信号：全部检查通过，且 diff 仅含目标生产区域、测试和本重构档案。
- 验证责任：AI 自证。
- 回滚：按步骤反向还原。

## 4. 风险与看点

- 最高风险是异步调用顺序漂移：价格退出必须继续短路多空比/OI；OI 请求仍只在 LONG、最新多空比大于 1、阈值大于 0 时发生。
- `close_bn_position()` 调用后必须阻止同轮进入 DCA/动态目标更新。
- DCA 在下单失败时必须撤销本轮追加的 `PositionSide.DCA`；成功后均价查询失败仍只发消息，不伪造均价。
- 按 sheet 分组必须保持每个 sheet 内记录的原提交顺序，不能使用会重排记录的集合。
- 删除同步入口属于内部接口清理；仓库中的其他历史脚本拥有各自同名类，不在本次范围，也不受影响。
