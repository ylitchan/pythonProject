---
type: issue
status: complete
updated: 2026-09-08
---

# AUTOA 状态与执行顺序修复

## 目标

落实本轮审查建议：解除平仓对交易日历的依赖；先完成状态更新和记录入队再通知；收盘更新完成后保存；整理指标、行情和调度重复代码。用户明确保留零方差的现有行为。

本轮追加（2026-09-08）：修复 ATR=NaN 误建仓；同批冷却确认复用一次交易日历请求；AUTOA ATR 只遍历所需窗口；直接分片观察列表；去掉无证据的每轮全量 GC；先测量保存耗时再选择最小优化。遵循用户“正确、清晰、单一语义、按数据依赖与副作用安排顺序”的要求，不新增共享可变中间状态。

## 现场

- 基线：`dev@988bd45f`；工作区已有 `tokenDemo/close_records.xlsx` 修改，保留。
- 已复现：日历不可用时现价 4.5 跌破止损 5 仍不平仓；通知取消造成 DCA 未保存或平仓记录缺失；收盘内存 price=7 而保存快照仍为 5。
- 现有 AUTOA 定向测试 41 项通过；不能替代上述异常路径验证。
- `.codestable/attention.md` 为空，无可用 lesson。项目切比雪夫旧文档只作背景，不改变当前计算口径。

## 边界

- 保留 BZ 硬重置/后续最低价累计、N 建仓复制止损且持仓止损固定、T+1 限制和非 N 原有风控。
- 零方差和两套 ATR 各自算法不变；复用计算不改变 AUTOBN 策略。
- 用户后续明确：不处理旧数据，不加 BZ 数据迁移或初始化限制。
- 沿用 unittest 测试设施，新增 `tokenDemo/test_autoa_state_flow.py` 覆盖故障路径；不调用真实行情、通知或交易，不修改业务 JSON/Excel；不自动推送。
- 另一个任务正在同文件整理 AUTOBN，保留其修改；当前任务只改 AUTOA、共用概率结果、观察冷却字段和记录入队/刷盘。

## 证据

- 审查位置（基线）：`autoTrade_pm.py:3255` 日历阻断退出；`:3185` / `:3280` 通知中断；`:3452` 先保存后更新。
- `python -B -m unittest tokenDemo.test_autoa_state_flow` 最初 4 项失败：日历阻断退出、通知取消、收盘快照落后；现已转绿。
- 已完成基线回归 188 项通过；新增重启、原子保存和行情复用测试 11 项通过。最终测试与审查待记录。
- 2026-09-08：主策略、状态流程、凭证及通知测试合计 196 项通过；ruff F 检查通过；回测指标对照 381 点 ATR/BZ/N 无差异。
- 冻结审查目标：基线 `988bd45f5ee238b9a6bda378fcfd38c49482ddee`；当前工作区 AUTOA、Observation、共用概率结果、CloseRecordManager 及两种概率包装。LF 标准化后顺序拼接 Observation→AUTOBN 之前、AUTOBN 概率包装、AUTOA→文件尾，SHA256=`E1957DA022AAF15625E22E3399CB99CC5CC9940C3E0BCFF2ED9DADDC9D964EB9`。
- reviewer 创建方式：`collaboration-optimize.spawn_agent`，显式 `gpt-6-astra/high`，最强可用模型；独立审查排除并发任务的 AUTOBN 仓位重构和业务 Excel。
- 第一轮审查发现：启动入口仍被日历故障阻断、退出时保存异常跳过清理。已新增故障回归并修复，额外要求降级行情有当日历史佐证且不能 DCA/新开仓。
- 第二轮冻结范围 SHA256=`A20F1E3BEA01057E9C88F477DFDACF1802B25B5918C952C419B9FB39A7C7A1F3`；新测试 SHA256=`503B80BEAA1D788DD09C32375CF0FC8DFBE6A37740D408B8BE21E38FE477BAC8`。同一 reviewer lineage 复审。
- 修复后 200 项测试通过、ruff F 与 diff 检查通过。
- 第二轮独立审查通过：原两项 resolved，unresolved/new findings 均无；reviewer 另复跑 59 项状态流程、AUTOA 与记录管理测试通过。run identity：`/root/review_autoa_flow`。
- 可复现命令：`.venv/Scripts/python.exe -B -m unittest tokenDemo.test_autoTrade_pm tokenDemo.test_autoa_state_flow tokenDemo.test_env_credentials tokenDemo.test_pushplus_notifications`；`.venv/Scripts/python.exe -B tokenDemo/test_backtest_autoa_parity.py`；`.venv/Scripts/python.exe -B -m ruff check --no-cache --select F tokenDemo/autoTrade_pm.py tokenDemo/test_autoa_state_flow.py`。

## 验收

- [x] 日历失败仍退出并记录；恢复后按实际交易日解除冷却，之前不能重开。
- [x] 通知取消/失败不丢失 DCA 状态或平仓记录；通知内容与更新后的状态一致。
- [x] 收盘最终快照保存新状态，保存失败不破坏旧文件。
- [x] 模块导入无业务文件读写/退出保存/信号注册；程序显式初始化。
- [x] 旧数据兼容处理已按用户要求排除；N 已有止损保持固定。
- [x] 复用行情解析、切比雪夫核心；ATR 口径不变；简化变量及调度顺序，更新注释。
- [x] 相关回归、完整测试和独立审查通过。

### 本轮追加验收

- [x] 非正值、NaN、无穷 ATR 不建仓；有效 ATR 保持原 BZ/N 决策。
- [x] 同批多个待确认冷却只请求一次日历，失败不逐标的重试；已有持仓退出不等待该请求。
- [x] ATR 窗口优化数值与原实现一致，观察分片覆盖且不重复，取消/快照规则保持。
- [x] 记录保存与 GC 的实际耗时，避免为小收益增加后台线程或共享状态。
- [x] 回归及独立审查通过，更新流程文档。

本轮证据：新增 `AutoAEntryAndBatchEfficiencyTest`，原实现出现 NaN/无穷误建仓、8 次日历查询及持仓等待超时，修改后全部通过。主测试/状态/凭证/通知共 204 项通过；ruff F、diff 检查通过。指标回测 381 点无差异；ATR 5 种历史长度×4 种周期与修改前结果完全一致。

本机定向测量（仅临时文件/合成记录）：900 条观察、323155 字节，12 次保存中位耗时从 18.77ms 降至 7.75ms，前后文件字节一致；每轮完整 GC 的 8 次中位耗时约 60.31ms，已移除。60 根行情、5 周期 ATR 重复 2000 次，从约 97.61ms 降至 62.24ms。这些是该环境下的测量，不作线上耗时保证。保存只采用一次序列化/写入的直接优化，保留同步原子替换，无新增共享写任务。

本轮独立 change review：fresh reviewer，`collaboration-optimize.spawn_agent`，显式模型 `gpt-6-astra/high`（最强可用稳定模型）。冻结 `autoTrade_pm.py` 的 AUTOA→EOF（CRLF 统一为 LF），SHA256=`3D808D37BD2E319AA1514588EB51E729F8E663AD351CB32E9EBB56F095300C50`，同时检查新增 math 导入/移除 gc；状态测试 SHA256=`E46BA9BD7142F6EBD69AABAD28F43863E1551B8E120B91CBD722232B9E97935F`。并发任务的 AUTOBN 代码排除，原有未提交变更保留。

本轮审查通过（`/root/review_autoa_efficiency`），无 blocking/important/nit；reviewer 独立执行 20 项状态测试，以及日历等待取消、嵌套观察任务取消两条路径，均通过。优化后再以 `988bd45f` 原方法对照 900 组开仓和 900 组持仓有效行情，交易决策、持仓价格、DCA、退出原因和通知渠道一致（排除已授权改变的冷却记录表示及通知文本）。

推送前验证：另一任务已独立提交 `8fd36613`；本任务在其基础上合并验证主策略、AUTOA 状态、AUTOBN 仓位/效率、凭证及通知共 221 项全部通过，指标对照与 ruff F 通过。AUTOA 审查范围哈希未变；本提交只包含 AUTOA 及共用概率方法的剩余变更、测试、文档和本游标。

## 状态与未决

前一轮与本轮追加均完成，本次按用户要求交付代码、测试、说明文档与保留的 work 游标。零方差逻辑与旧数据处理按用户要求保留；交付不包含业务 Excel 和并发任务的 AUTOBN 仓位/效率重构。

毕业去向：状态顺序、冷却恢复、降级退出、原子保存、初始化和复用约定已写入 `tokenDemo/autoTrade_pm_AUTOA状态流程.md`，本轮补充异常 ATR 拦截、日历批次快照、ATR 窗口与单次序列化约定；旧文件写入文档增加指向新流程的说明。异常场景不变量由 `tokenDemo/test_autoa_state_flow.py` 回归覆盖，不另建 lesson。

work 游标按用户要求保留。无本任务未决实现项；尚未刷盘时的强杀/断电和失败通知重发不在此次保证范围，已在流程文档说明。
