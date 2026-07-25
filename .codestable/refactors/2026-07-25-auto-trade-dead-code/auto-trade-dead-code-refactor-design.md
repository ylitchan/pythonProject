---
doc_type: refactor-design
refactor: 2026-07-25-auto-trade-dead-code
status: approved
scope: tokenDemo/autoTrade_pm.py 中静态可证明的无用代码
summary: 删除无用导入、零引用私有包装、无效临时变量及无用参数，保持行为等价
---

# auto-trade-dead-code refactor design

## 1. 本次范围

- 执行 scan #1～#7。
- 只改 `tokenDemo/autoTrade_pm.py` 与本次 CodeStable 记录。
- 不改交易条件、异常处理、公开返回值和调度行为。
- 总体风险：低。

## 2. 前置依赖

- Ruff 已确认 `copy` 为 F401。
- Vulture 已确认 `fields`、`frame` 未使用。
- 全仓搜索已确认三个私有 PAPI 包装方法零调用。
- 现有 53 个单测及 AUTOA parity 可用于行为等价验证。

## 3. 执行顺序

### 步骤 1：删除无用导入和无效局部赋值

- 引用方法：M-L2-03 Replace Temp with Query
- 具体操作：删除 `copy`、`send_msg` 第一次会话获取、`_manage_position` 第二次无用 `is_long`。
- 退出信号：Ruff 不再报告 F401/F841；53 个单测通过。
- 验证责任：AI 自证。
- 回滚：恢复对应单行。

### 步骤 2：删除零引用私有包装方法

- 引用方法：M-L2-02 Inline Function
- 具体操作：删除 `_new_order_via_papi`、`_change_leverage_via_papi`、`_call_um`；实际调用继续使用 `_call_api`。
- 退出信号：全仓搜索三个名称为 0；53 个单测通过。
- 验证责任：AI 自证。
- 回滚：恢复三个方法。

### 步骤 3：收窄未使用参数

- 引用方法：M-L1-01 Parallel Change
- 具体操作：确认调用方后删除 `stock_zh_a_hist.fields`；将信号协议参数 `frame` 重命名为 `_frame`，保持双参数签名。
- 退出信号：Vulture 复扫不再报告两项；AUTOA parity 与 53 个单测通过。
- 验证责任：AI 自证。
- 回滚：恢复参数签名。

### 步骤 4：机械收口与全量验证

- 引用方法：M-L2-02 Inline Function（删除后的机械收口）
- 具体操作：只整理变更邻域空白，不全文件格式化。
- 退出信号：Ruff 静态检查通过；Vulture 高置信扫描无本轮目标；53 个单测和 AUTOA parity 全部通过；diff 仅含约定删除。
- 验证责任：AI 自证。
- 回滚：按 diff 恢复空白。

## 4. 风险与看点

- `fields` 虽属方法参数，但所有项目调用方均未传入；删除前再做一次全仓搜索。
- `_frame` 仍保留信号回调要求的两个位置参数，不改变运行行为。
- 不依据 Vulture 对框架入口、枚举或动态调用的推测删除任何其他成员。
