---
type: issue
status: in_progress
updated: 2026-09-10
---

# AUTOBN 币安请求限流排查

## 目标

2026-09-10 用户明确同意加入临时真实请求诊断：统计实际HTTP发送（含SDK额外尝试）、1/5分钟接口与周期计数、缓存命中/滞后重取、预筛通过数量、429/418及安全权重响应头。日志为tokenDemo/binance_requests.log，轮转限大小；不修改交易规则、缓存策略或退避，不额外请求币安，不重启、不自动提交推送。定位后移除临时埋点并清理日志，当前保留供用户重启取证。

诊断归属：BinanceGateway拥有请求观测，通过SDK实际requests Session.send边界计数，行情缓存和扫描阶段只提交诊断标签。统计线程安全、有界内存；日志只输出固定接口名、周期、合法symbol、计数/数值头，不记录密钥、签名、body、完整URL或自由文本异常。日志异常不能改变真实请求结果。uv本地纯mock验证，最终独立审查。

解释 `tokenDemo/autoTrade_pm.py` 在币安返回 `TooManyRequestsError(-1003)` 时为什么出现单分钟少量标的成功，以及区分扫描超时与 API 限流。

## 现场

- 日志显示 BN 扫描批次约 130–145 个标的，单批总耗时约 1.8 秒，并非 `MARKET_ANALYSIS_TIMEOUT=55` 秒超时。
- 失败集中在 `get_kline()` 的请求，错误来自币安 IP 级限流；该异常被捕获后该标的返回空 K 线，不计入成功数。
- 当前进程检查到一个实际 `autoTrade_pm.py` 实例；另一个 PID 是 Windows 虚拟环境解释器启动器，不是第二个扫描任务。

## 边界

- 本轮只诊断，不改 `autoTrade_pm.py`、配置、测试或运行中的进程。
- 不凭本机静态代码推断共享出口 IP 的其他流量；需要运行时请求权重/响应头或网关监控才能证明完整额度来源。

## 证据

- 2026-09-10 本次临时诊断实现：requests Session.send实例包装，SDK调用通过threadlocal归属额外发送，ContextVar标识held/observed/unobserved/pending，按monotonic秒桶统计近60/300秒。本进程首次429和首次418各立即输出安全统计，持续故障不逐请求刷日志；有HTTP活动每60秒输出minute_summary。extra_sends包括同SDK调用内的额外发送（通常SDK重试，也可能重定向），不是额外下单数，不等于币安实际收到的请求数。
- 输出安全边界：只记录映射后的固定endpoint、允许的period/HTTP method、来源service、扫描类别和安全symbol；仅保留数值X-MBX/X-SAPI使用量/订单计数/Retry-After头。不会输出请求完整URL、signature、API key、body、cookies、任意异常字符串。输出含observed_seconds，运行不足5分钟时不能将计数误认成完整窗口。
- 验证：新增首3项测试红色缺实现后转绿；现90项测试通过，包括真实SDK但mock网络的1次调用2次发送、并发100次准确计数、滚动窗口淘汰、缓存滞后/命中、429→418分别首报与抑制、日志5MiB+2备份/懒创建、日志失败不改变原返回或异常、敏感内容不进入日志。无真实币安请求；测试日志均在临时目录且已清理，仓库未生成诊断运行日志。
- 无业务变更：TradingState、TradeExecutor、BinanceExecutor、AshareExecutor、AUTOA及A股数据源AST与HEAD完全相同；其余仅添加诊断作用域/计数及HTTP调用包装，未新增缓存、节流或重试。Ruff F/compile/diff检查通过。等待独立review与用户重启取证；此前故障不能靠新统计回溯补齐。

- `AUTOBN.BATCH_WINDOW_MINUTES=5`、`BATCH_SLOT_COUNT=5`，扫描固定快照的一个 slot；723 个快照对应约 145 个标的/分钟。
- `_call_api()` 只有 `asyncio.Semaphore(8)` 并发闸门和单次 15 秒超时，没有按分钟/权重的速率限制或退避；批次通过 `asyncio.gather()` 集中发起。
- 每个标的至少请求一次日 K；满足观察/信号条件时还会请求 1d/5m OI、1h/5m 多空比、基差等多个接口，持仓或开仓路径还会增加账户/交易请求。
- `max_instances=1` 只防 APScheduler 的同一任务重叠，不限制同 IP 的其他进程、机器或服务。
- `uv run --no-sync python -B -m unittest tokenDemo.test_autobn_efficiency`：8 项通过；`tokenDemo.test_autoTrade_pm.AutoBNCharacterizationTest`：82 项通过。

## 验收

- [x] 结论能解释截图中的 `-1003`、批次数量与成功数量。
- [x] 明确指出当前证据不能证明本机单进程独自消耗完 24000/min，需要运行时请求权重和出口 IP 维度数据。
- [x] 无产品 diff、无临时产物、无运行中进程变更。

## 状态与未决

当前状态（2026-09-10）：用户已授权临时诊断，正在验收；需要重启后生成tokenDemo/binance_requests.log才能确定真实限流来源。此文件及.1/.2已gitignore，当前代码未commit/push、未自动重启。以下2026-09-08结论仅为旧现场历史，不构成此次统计端点触限的确证。

- 本次诊断代码验收完成：fresh reviewer `/root/review_binance_diagnostics`，collaboration-optimize.spawn_agent，异构gpt-5.6-sol/high，无回退。冻结源 `F1BD57E17CE12B811D66FF7278B5F2A961673D77A94A826ACDFC24139234CDC2`、测试 `516018485D3024F9B9049C7AB253EC3985E8F28281030063CCF4510A14050320`、gitignore `640098D6858562E0F242078758CDE985C7CA624D26309EFABEDD8A79C5390D5B`，独立90测试通过、终态可合，无blocking/important/nit。诊断计数1万次模拟更新约0.013秒，仅代表本机计数部分；无真实网络取证或日志写入业务目录。
- 下一步：用户确认封禁解除后重启新脚本，先收集活动期间至少5分钟的minute_summary；出现首次限流可检查rate_limit的trigger、接口周期/来源、extra_sends及server_headers。无需故意触发封禁。对日志缺失的响应头、共享出口其他流量不做未经证实推断；本次只修复缺少诊断证据的问题，尚未改变缓存频率、重试或全局退避。
- 清理：单元测试的轮转日志均在TemporaryDirectory内并已清理；诊断埋点按用户授权保留至现场原因确定，再移除埋点和binance_requests.log及两份备份。未提交/推送本轮代码，未停止或重启现有交易进程。

已完成诊断。根因结论：请求被币安按 IP 的分钟权重限流；代码的 8 并发和 5 分钟分批只限制同时运行的任务数量，不是速率/权重配额。若要修复，应在统一 `_call_api()` 入口增加权重感知限速/退避，并优先用 WebSocket 提供实时行情；具体权重表和同出口其他流量需从响应头或网关监控补证。

毕业去向：本次结论留在该 issue work 游标；无 lesson 或产品文档需要沉淀。
