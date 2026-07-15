# .env 凭证与 PushPlus SDK 迁移验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-07-15
> 关联方案 doc：`.codestable/features/2026-07-15-env-sdk-credentials/env-sdk-credentials-design.md`

## 1. 接口契约核对

- [x] `AUTOBN.from_cfg`：Binance 凭证只接受显式参数或 `BINANCE_API_KEY` / `BINANCE_API_SECRET`；显式值优先，三项刻画测试通过。
- [x] 环境变量契约：`.env.example` 包含四个约定变量且全部为空；本地 `.env` 已加载并被 Git 忽略。
- [x] `TradeNotification`、格式化和分类接口未变，既有 Markdown 输出测试保持通过。
- [x] `send_pushplus`：移除 HTTP session 参数，使用 token 和可选 secret key 构造官方 SDK 客户端；token 缺失返回 `False`。
- [x] 流程图节点均有落点：入口加载 `.env`、Binance 初始化、SDK 客户端缓存、工作线程发送、通道边界异常日志。

## 2. 行为与决策核对

- [x] Binance 生产入口不再传 `bn.json`；源码中 `bn_api_file` 引用为零。
- [x] PushPlus 使用 `perk-pushplus-sdk==1.0.1` 的 `PushPlusClient`、`SendRequest` 和 `Template.MARKDOWN`，不再自行维护 `/send` 请求。
- [x] SDK 是同步 `requests` 实现，发送通过 `asyncio.to_thread` 执行，不阻塞异步调度器。
- [x] SDK 客户端按 token/secret key 缓存，符合官方线程安全、长期复用建议。
- [x] `PUSHPLUS_SECRET_KEY` 已纳入配置；根据官方契约，它仅开放接口必需，普通消息在其为空时仍可发送。
- [x] AUTOBN/AUTOA 事件筛选、Markdown 文案、企业微信 HTTP 和通知失败隔离均保持不变。
- [x] 未引入重试、队列、交易策略改动、消息范围扩大或 HTML 模板。

**挂载点反向核对**：

- [x] `.env` 加载位于程序入口，路径由源码位置解析，不依赖启动目录。
- [x] Binance 环境凭证解析位于 `AUTOBN.from_cfg`。
- [x] SDK 构建、请求构造与发送全部收敛在 `pushplus_notifications.py`。
- [x] `.gitignore` 与 `.env.example` 覆盖秘密保护和配置契约。
- [x] grep 未发现 PushPlus URL、通知模块 `session.post`、旧 `send_pushplus(http_session, ...)` 或 `bn_api_file` 残留；拔除上述四个挂载点即可移除本次能力演进。

## 3. 验收场景核对

- [x] **S1 `.env` Binance 初始化**：本地凭证已从被忽略的 `tokenDemo/bn.json` 迁移至根目录 `.env`；环境读取测试通过。
- [x] **S2 显式参数覆盖**：显式 key/secret 覆盖环境值测试通过。
- [x] **S3 缺失 Binance 凭证**：明确抛出指向两个变量的 `ValueError`，且测试保证不读取 `bn.json`。
- [x] **S4 SDK Markdown 请求**：mock 官方 builder/client 验证 token、secret key、标题、正文和 `Template.MARKDOWN`。
- [x] **S5 secret key 可选**：未配置 secret key 时不调用 builder 的开放接口配置，普通消息仍发送。
- [x] **S6 token 缺失**：返回 `False` 且 SDK 发送函数不调用。
- [x] **S7 异步与失败语义**：验证 `asyncio.to_thread` 被等待；SDK 异常不包含测试凭证并由既有 `send_msg` 边界捕获。
- [x] **S8 原行为保持**：57 项凭证、通知和交易回归测试全部通过。
- [x] **S9 真实通道**：`uv run python -m tokenDemo.test_pushplus` 返回 `{"code": 200, "msg": "SDK Markdown 推送成功"}`。
- [x] **S10 安全边界**：`.env` 被忽略且未跟踪，`.env.example` 无真实值，编译和反向检查通过。

## 4. 术语一致性

- 环境变量名统一为 `BINANCE_API_KEY`、`BINANCE_API_SECRET`、`PUSHPLUS_TOKEN`、`PUSHPLUS_SECRET_KEY`。
- SDK 名称区分明确：安装名 `perk-pushplus-sdk`，Python 导入名 `perk_pushplus`。
- `TradeNotification`、AUTOBN、AUTOA、N 策略等既有术语未改名。
- 旧术语 `bn_api_file` 在本次生产与测试范围内无残留。

## 5. 领域影响盘点

- [x] `.env` 和 SDK 是运行配置/基础设施实现，不是交易领域新实体，无需写入 CONTEXT。
- [x] 使用官方 PushPlus SDK 替代自写 HTTP 是可回退的局部依赖选择，不满足单独 ADR 的必要性。
- [x] “通知失败不影响交易”是已有 requirement 边界，本次没有新增流程级领域约束。

## 6. requirement 回写

- [x] `trade-push-notifications` 已是 current；本次更新“凭证来自环境或 `.env` 且不进入版本控制”的边界，并追加 2026-07-15 变更日志，原愿景和通知范围保留。
- [x] `requirements/VISION.md` 状态不变，无需调整。

## 7. roadmap 回写

- [x] 本 feature 非 roadmap 起头，方案无 `roadmap` / `roadmap_item`，无需回写。

## 8. attention.md 候选盘点

- [x] 候选：官方 Python SDK 的安装名是 `perk-pushplus-sdk`，导入名是 `perk_pushplus`；截图只显示导入名时直接 `uv add perk-pushplus` 会解析失败。该信息与具体集成高度相关，已由 `pyproject.toml` 固化，不必加入全局 attention。

## 9. 遗留

- 后续优化点：无。
- 已知限制：`PUSHPLUS_SECRET_KEY` 当前本地为空；普通消息发送不需要它，未来调用 PushPlus 开放接口前需要在 `.env` 补齐。
- 实现阶段顺手发现：无。
