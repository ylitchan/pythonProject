---
doc_type: refactor-scan
refactor: 2026-07-11-auto-trade-core
status: user-reviewed
scope: tokenDemo/autoTrade_pm.py 中 CloseRecordManager 与 AUTOBN.rzq_token，以及 tokenDemo/test_autoTrade_pm.py 对应测试
summary: 发现并确认 3 条优化点：可读性 2 条、性能 1 条；低风险 1 条、中风险 1 条、高风险 1 条
---

# auto-trade-core scan

## 总览

- 扫描范围：`tokenDemo/autoTrade_pm.py` 的 `CloseRecordManager`、`AUTOBN.rzq_token()`；`tokenDemo/test_autoTrade_pm.py` 对应测试
- 发现 3 条优化点：可读性 2 / 性能 1
- 按风险：低 1 / 中 1 / 高 1
- 建议顺序：#1 删除同步旧入口 → #2 按 sheet 聚合批次 → #3 补测试后拆 `rzq_token()`
- 建议慎做：#3 涉及交易分支和异步调用顺序，必须先补刻画测试并分步提取
- 前置检查：范围已从超过 3000 行的整文件缩至两个类的目标区域；测试文件存在，关键退出条件已有部分覆盖；本次不改交易行为
- 用户选择：2026-07-11 已明确确认 #1、#2、#3 全部执行

## 条目

### [#1] 删除同步平仓记录旧入口 ✓

- **位置**：`tokenDemo/autoTrade_pm.py:173-262`、`tokenDemo/test_autoTrade_pm.py:196-226`
- **分类**：可读性
- **现状**：生产路径只调用 `record_close_async()`，同步 `record_close()` 仅被一项测试调用，并独立维护一套记录构造和 Excel 写入逻辑。
- **问题**：同一 Excel 契约存在两套约 90 行实现；字段、格式或错误语义修改时需要双处同步，生产代码中同步入口调用数为 0。
- **建议**：让格式测试直接调用 `_record_close_batch()`，全仓确认目标方法零引用后删除 `record_close()`。
- **建议映射的方法**：M-L2-02（Inline Function）
- **风险**：低（目标入口无生产调用，grep 和既有 Excel 格式测试可自证）
- **验证**：AI 自证（全仓 grep `CloseRecordManager.record_close(` 为 0；运行 CloseRecordManager 测试）
- **范围**：约 95 行 / 2 文件

### [#2] 按 sheet 聚合批次记录 ✓

- **位置**：`tokenDemo/autoTrade_pm.py:264-285`
- **分类**：性能
- **现状**：`_record_close_batch()` 对每条记录构造单行 DataFrame，并立即与目标 sheet 执行一次 `pd.concat`。
- **问题**：同批同 sheet 有 N 条记录时执行 N 次 DataFrame 构造和 concat；随着批次增大产生重复拷贝，而批次提交顺序本可在分组列表中保持。
- **建议**：先按 sheet 将记录追加到有序列表，每个 sheet 构造一个 DataFrame 并只 concat 一次；保留原 sheet 和批次内记录顺序。
- **建议映射的方法**：M-L4-02（Batching）
- **风险**：中（运行特征变化，但输出工作簿、列和顺序可用测试锁定）
- **验证**：AI 自证（新增同 sheet/跨 sheet 顺序测试；mock `pd.concat` 验证每个目标 sheet 一次；运行 CloseRecordManager 测试）
- **范围**：约 25 行 / 2 文件

### [#3] 提取 rzq_token 持仓处理职责 ✓

- **位置**：`tokenDemo/autoTrade_pm.py:1629-1981`
- **分类**：可读性
- **现状**：`rzq_token()` 的持仓分支约 320 行，连续包含 ATR 初始化、价格/OI/多空比退出判断、平仓执行、LONG/SHORT DCA、止盈衰减和追踪止损更新。
- **问题**：单函数远超 50 行，多个异步副作用与条件优先级交织；目前测试覆盖当前价止损和部分 OI 条件，但尚未完整锁定“价格退出时不请求多空比”“OI 优先于多空比”“平仓后不再 DCA/更新目标”“LONG/SHORT DCA 失败回滚”等顺序契约。
- **建议**：先补关键分支刻画测试，再依次提取持仓退出判断/执行、LONG 管理、SHORT 管理等内部方法；`rzq_token()` 保留数据获取及 position/observation 顶层分派，提取期间不改参数含义和调用顺序。
- **建议映射的方法**：M-L1-04（Characterization Test）+ M-L2-01（Extract Function）+ M-L2-05（Decompose Conditional）
- **风险**：高（交易判断和异步 API 顺序属于外部可观察行为，任何提前 return 或调用重排都可能改变交易）
- **验证**：AI 自证（新增分支优先级、API 调用、状态写回、LONG/SHORT DCA 与动态目标测试；每次提取后运行 AutoBN 目标测试，最终运行全文件测试）
- **范围**：约 350 行 / 2 文件
