---
doc_type: refactor-scan
refactor: 2026-07-25-auto-trade-dead-code
status: user-reviewed
scope: tokenDemo/autoTrade_pm.py 中由 Ruff/Vulture 与全仓引用搜索静态证明的无用代码
summary: 发现 7 条：可读性 7；低风险 7
---

# auto-trade-dead-code scan

## 总览

- 扫描范围：`tokenDemo/autoTrade_pm.py` 的静态可证明项；不扫描策略条件、不改公开行为
- 发现 7 条优化点：可读性 7 / 结构 0 / 性能 0
- 按风险：低 7 / 中 0 / 高 0
- 建议先做：#1～#7，均有静态证据且可由 53 个现有单测与 AUTOA parity 自证
- 建议慎做 / 后做：不删除仅凭命名猜测的常量、公开方法或策略分支
- 前置检查：用户已主动把原 3,500+ 行全文件扫描缩到“静态可证明项”；测试覆盖、第三方代码、跨模块等其余检查通过

## 条目

### #1 删除无用 `copy` 导入

- **位置**：`tokenDemo/autoTrade_pm.py:4`
- **分类**：可读性
- **现状**：导入 `copy` 后全文件未使用。
- **问题**：Ruff `F401` 明确报告 1 个无用导入。
- **建议**：删除 `import copy`。
- **建议映射的方法**：M-L2-02 Inline Function（去除无作用间接层的同类行为等价删除）
- **风险**：低；Python 名称解析证明无调用。
- **验证**：AI 自证（Ruff F401 + 单测）
- **范围**：1 行 / 1 文件

### #2 删除三个零引用 PAPI 包装方法

- **位置**：`tokenDemo/autoTrade_pm.py:591-608,718-720`
- **分类**：可读性
- **现状**：`_new_order_via_papi`、`_change_leverage_via_papi`、`_call_um` 仅有定义；实际调用全部直接走 `_call_api`。
- **问题**：全仓搜索每个名称均只有 1 次定义、0 次调用，共 21 行死包装代码。
- **建议**：删除三个私有包装方法，保留实际使用的 `_call_api` 与枚举转换方法。
- **建议映射的方法**：M-L2-02 Inline Function
- **风险**：低；均为下划线私有方法，且全仓零引用。
- **验证**：AI 自证（grep 名称 0 引用 + 53 单测）
- **范围**：约 21 行 / 1 文件

### #3 删除 `_manage_position` 无用局部变量

- **位置**：`tokenDemo/autoTrade_pm.py:1879`
- **分类**：可读性
- **现状**：第二次计算 `is_long` 后不再读取；分支直接重新比较 `position_side`。
- **问题**：该赋值没有任何消费点，形成误导性的状态变量。
- **建议**：删除第二次 `is_long = ...`，保留 ATR 初始化分支内实际使用的同名变量。
- **建议映射的方法**：M-L2-03 Replace Temp with Query（删除已被直接查询替代的临时变量）
- **风险**：低；数据流证明赋值后零读取。
- **验证**：AI 自证（单测）
- **范围**：1 行 / 1 文件

### #4 删除 `send_msg` 重复会话获取

- **位置**：`tokenDemo/autoTrade_pm.py:640,671`
- **分类**：可读性
- **现状**：函数开头获取 `http_session`，中间未使用；发送请求前再次获取并覆盖同名变量。
- **问题**：第一次赋值 31 行内零读取且必被第二次赋值覆盖。
- **建议**：删除第一次 `http_session = await self._get_http_session()`，保留请求前的获取。
- **建议映射的方法**：M-L2-03 Replace Temp with Query
- **风险**：低；`_get_http_session` 只创建/返回会话，真正使用发生在保留的第二次调用。
- **验证**：AI 自证（消息测试相关单测 + 全量单测）
- **范围**：1 行 / 1 文件

### #5 删除 `stock_zh_a_hist` 无用 `fields` 参数

- **位置**：`tokenDemo/autoTrade_pm.py:2888-2896`
- **分类**：可读性
- **现状**：`fields` 参数在方法体内从未读取，文件内 4 个调用点也均未传入。
- **问题**：Vulture 100% confidence 报告无用参数；全仓不存在对该类方法传 `fields=` 的调用。
- **建议**：从私有项目类方法签名删除 `fields` 参数。
- **建议映射的方法**：M-L1-01 Parallel Change（先核对全部调用方，再收窄签名）
- **风险**：低；调用方全在同文件且均使用默认位置参数。
- **验证**：AI 自证（grep 调用点 + AUTOA parity + 单测）
- **范围**：1 行 / 1 文件

### #6 将信号处理器未使用参数标记为刻意忽略

- **位置**：`tokenDemo/autoTrade_pm.py:3538`
- **分类**：可读性
- **现状**：`signal.signal` 回调协议必须接收 `frame`，实现不读取它。
- **问题**：Vulture 100% confidence 报告无用参数，但该参数不能从回调签名删除。
- **建议**：将 `frame` 重命名为 `_frame`，明确它是协议要求但刻意未使用。
- **建议映射的方法**：M-L2-03 Extract Variable（用显式忽略名表达参数角色）
- **风险**：低；参数位置和回调 arity 不变。
- **验证**：AI 自证（Vulture 复扫 + 单测）
- **范围**：1 行 / 1 文件

### #7 清理由前述删除产生的空白冗余

- **位置**：`tokenDemo/autoTrade_pm.py` 上述方法边界
- **分类**：可读性
- **现状**：删除包装方法后可能留下连续多余空行。
- **问题**：会形成不符合 Python 顶层/类方法间距的局部格式噪声。
- **建议**：仅对变更邻域运行 Ruff formatter，不格式化全文件。
- **建议映射的方法**：M-L2-02 Inline Function（删除后的机械收口）
- **风险**：低；只调整空白。
- **验证**：AI 自证（`ruff format --check` 变更邻域人工 diff 复核）
- **范围**：约 1-4 行 / 1 文件
