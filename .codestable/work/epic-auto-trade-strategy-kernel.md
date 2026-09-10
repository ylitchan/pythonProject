---
epic: ../epics/auto-trade-strategy-kernel.md
phase: acceptance
approved_revision: 89D8398E2ABDD88543E61585A448925DC885D3EEC556152A37BAD9E14C67A89A
current_item: null
next_action: 持仓恢复修复已验收，按用户本次授权推送origin/dev；限流仅完成诊断，未改请求策略
blocked_by: null
item_progression: continuous
milestone_commit: manual
remote_publish: manual
---
## 子项进度

- [x] ITEM-1
- [x] ITEM-2
- [x] ITEM-3
- [x] ITEM-4
- [x] ITEM-5
- [x] ITEM-6
- [x] ITEM-7
- [x] ITEM-8
- [x] ITEM-9

## 临时决策与证据

- 2026-09-10 用户因同花顺批量过期/502要求恢复三源：腾讯历史及当日行情、东方财富涨停池、新浪交易日历，优先稳定性。按cs-issue仅修改A股数据适配与测试；保留未提交币安诊断、恢复代码和其他用户文件。不恢复大型AkShare默认依赖；新浪日历采用标准库位流解码，实际8797日期与现有AkShare参考全量相同。无自动重启/交易/提交推送。

- 2026-09-10 恢复修复完成：guard恢复按max(最近30根1h OI、最新5m OI)峰值，原样本剔除末6根计算mean+10std，min两种上界；恢复后已跌破阈值立即生成全平，有效guard不动。完全缺JSON/日志的真实仓位纳入N恢复，当前ATR轨道和实际方向/均价，不发送OPEN或伪造历史次数。方向冲突只保留退出，随后成功账户查询确认冲突消失即清理待恢复候选。
- 独立审查 `/root/review_full_position_recovery`（collaboration-optimize.spawn_agent，异构gpt-5.6-sol/high，无回退）R1两项已修复（冲突下DCA、错误symbol绑定），R2冲突候选残留已增加红色回归并修复；R3完整候选终态可合，无blocking/important/nit。82项新入口测试含原核心对照通过，Ruff F/编译/diff检查通过。源SHA `4F322FA278D2B6441DF97391A1A4BF9192E67F0E354D5F4CCAED70BDE5672140`，测试SHA `A40244CE2D1119011B8BAD0681AB3FAD4EEAFBD8B4440DDF32F33FA02A8D9C1A`。用户当轮推送授权有效，业务JSON/订单日志/Excel/AGENTS及其他任务游标排除。
- 限流只读核验：不调用真实币安API；模拟完整process_instrument路径在5m末根滞后时，无观察BD预筛每币3次（2次OI）、BZ确认未通过仍作BD判断7次（4次OI+2次多空比+K线）、完成开仓含1次补查14次。149标的全部落到同一路径的理论总数分别447/1043/2086，不是实际观测量，也不是请求权重；SDK统计接口限制1000次/5分钟，不能与每分钟总REST量直接等同。首次封禁来源缺时间窗口计数/响应头，不能据此认定。请求退避和缓存重试控制不在本次提交。


- 2026-09-10 owner进一步确认：恢复阈值用峰值而非已回落当前值，max(30hOI,latest5m)*0.9与原切比雪夫上界取min；跌破恢复阈值当轮全平。JSON和订单日志都缺失的策略账户实际仓位不能无人管理，启动/每日进入N恢复队列，按实际方向/均价与当前轨道及多仓OI建立N，未知历史次数不伪造。原guard修复review通过，扩展恢复review R1提出方向冲突仍可DCA及响应symbol缺校验，已修并新增测试；当前81项通过。
- 2026-09-10 owner授权“推送”本次恢复修复；业务JSON/订单日志/Excel及用户AGENTS.md排除。另问429缓存：截图实际是HTTP418 RateLimitBanError(-1003)，解封时间上海2026-09-10 10:50:57。仅离线核验SDK和模拟调用，没有为该限流诊断发送真实币安请求；模拟证实收到封禁仍请求后续币，OI/多空比末根落后时同周期5次检查仍5次请求（旧新均如此）。这只是请求放大机制，不证明IP封禁唯一来源；该问题未混入本次恢复代码。


- 2026-09-10 用户要求修复HAEDALUSDT遗留N+DCA多仓的零OI阈值。旧入口get_position_risk缺本地记录时创建N并默认guard=0，新入口只读取未恢复；关机是否为原始丢失原因未证实。按cs-issue在已有持仓管理边界修复，共用正常开仓阈值公式，只对缺失/非有限/非正多仓guard按窗口峰值恢复，保留已有正阈值；失败不DCA但退出规则继续，不改业务文件/真实订单，不自动commit/push。无可用ultracode，使用现有工具。

- 2026-09-09 owner 明确要求“推送”，本次授权覆盖已验证的新入口、对应测试、依赖调整及本Epic契约/游标；不包含运行数据或其他任务游标。实现提交 `eaf43ef2`（新增统一交易引擎与同花顺行情单文件入口），依赖提交 `f903d01d`（将AkShare迁移为旧脚本可选依赖），验收记录独立提交；目标为已核实的 `origin/dev`。提交前核验源/测试SHA仍为71项测试通过版本，lock/编译/diff检查通过，fetch确认无分支分歧；不改运行进程、业务JSON或Excel。此前“未提交/未推送”条目保留为相应阶段历史。

- 2026-09-09 用户追加截图 `GAIBUSDT / -1122 Invalid symbol status` 并要求获取标的池时过滤。按cs-issue核查公开exchangeInfo：旧条件命中723个（722 TRADING、1 PENDING_TRADING），唯一误命中为GAIBUSDT；根因为 `"TRADING" in status`。本轮只改正式池过滤为精确USDT/TRADING，不修改信号、持仓管理、订单确认/保存时序，不扩展限流或黑名单。
- 同一截图退出信号2已通过Python signal枚举及handler调用链核实为SIGINT，handler执行sys.exit(0)、退出清理及atexit；截图错误之后扫描正常结束，错误不直接触发退出。SIGINT通常Ctrl+C/IDE中断，不能仅凭日志确定发出者或证明磁盘保存成功。
- 非法状态过滤已完成：新增精确状态/计价币种回归先红后绿，已有持仓与pending始终参与扫描的保护回归通过。业务源码仅一处谓词改为 `quoteAsset == USDT && status == TRADING`；反向还原该行后SHA与上次冻结7D948...完全一致，证实其他交易算法/时序未变。全新入口71项、Ruff F、编译、diff检查通过；只读exchangeInfo经真实新过滤方法输出722个，GAIBUSDT不再入池。无新增周期请求/黑名单/状态字段，没有修改业务文件或运行进程；稳定规则及回归在入口和测试承载，无需额外说明文档或lesson。
- 本次最终入口SHA256 `23D2A29061A2EE5892BCFD4E1DC1000A6CC7418A20A5CF4E3344AB8B20EB409E`；测试 `B1B4CE4FE44D6B4139B10D0DA4EB720AD9EB2DE3795D82967D47A7C5B7C3EBA9`。正式池只收可交易USDT的契约未变，不触及持久化、并发或订单提交边界，采用实际元数据验证与定向/整体入口回归。

- 2026-09-09 用户在确认免费、来源统一优先及公开接口稳定性尚未长期验证后明确“先换来试试看”，授权同花顺替换全部A股数据输入。新输入使用同花顺完整OHLCV和前复权值；已说明长历史复权与新浪存在差异，算法保持不动。
- ITEM-9 范围：`AshareMarketData` 直连同花顺历史日线/当日日线/涨停池/实际交易日接口；移除新入口中的新浪、东方财富、腾讯及AkShare调用，复用现有aiohttp，不增加SDK；AkShare仅保留为旧脚本可选依赖。不会改Binance交易链、业务JSON/Excel、运行中的进程；不自动commit/push。
- 实施前基线：入口 `99618199C41042653F2CD7AF61E49201AE6505860FC160BD36EE996E489134C4`，测试 `EBCCC152AB6D42BA33BAACCA9C0AA6D0C0C1FC01C5A38587A2A7E1CBA463AF38`。免费公开接口已实证四项均返回；一次涨停池与原源46只完全一致，两个日期各前30/后40交易日与新浪完全一致，最近19个交易日3样本OHLC一致。长历史复权存在差异、部分请求曾502，必须有有界重试及新鲜度/完整性检查。
- 当前会话没有可用ultracode工具/技能；按cs-feat使用现有原生工具与独立change review。涉及交易输入和异步I/O的失败顺序，本次增加对应回归与审查，无额外说明文档。
- ITEM-9 本地验证：67项新入口测试通过（含620组原核心交易parity）；源切换新增6项先出现5个失败后转绿，再补8项日期/分页/缓存/取消边界。实际只读同花顺三样本分别返回20根当日有效K线、涨停池48只、日历前后交易日正常。隔离默认环境安装60包、不含AkShare，直接入口拦截main加载通过；可选依赖移动后的包版本与原uv.lock完全一致。Binance全类/执行器/引擎/TradingState和市场策略规则AST保持，AUTOA日报仅透传now。
- ITEM-9 契约审查：fresh `/root/review_ths_contract`，collaboration-optimize.spawn_agent、gpt-5.6-sol/high异构，无回退；R1提出日历覆盖不足与重试措辞，补两侧60条完整性验证并明确语法/schema边界后，R2终态可合，无blocking/important/nit。用户“先换来试试看”已明确授权本次来源口径及试用，无额外审批。
- ITEM-9 代码审查：fresh `/root/review_ths_implementation`，同样工具及模型，与契约阶段独立；R1唯一important为合法非对象JSON误重试，直接[]/JSONP callback([])两场景先红后绿；R2完整候选及增量复核终态可合，无blocking/important/nit。
- ITEM-9 最终入口SHA256 `7D948CE3E56340C3833AF2DD3E056DD3588FE6B3977A19F361509CF75D5EAFEE`；测试 `A39D46B76EF34899F98B96B2C48E8367295F846A63167F8C5F9D5B2D4AA30BFC`。69项测试通过，Ruff F/编译/diff/lock检查通过；默认无AkShare隔离62项通过（其余5项旧入口parity在旧依赖环境验证），optional extra隔离环境中新旧入口均加载成功。15:06:05仅实际数据调用：两只行情时效检查通过、完整涨停池48只；后续完整日历121条、收盘20根K线通过。
- 毕业去向：统一数据源契约为Epic DEC-20～22及ITEM-9，行为/错误边界为新入口测试；不新增说明文档或lesson。系统Temp `autotrade-ths-baseline-qwcog_av` 的4份临时基线在交付时清理。没有自动重启/停止实盘进程，没有下单/推送通知，没有直接写业务JSON/Excel，旧入口维持1375716b，未commit/push。

- 2026-09-09 用户授权修复详细审查发现的四项问题，并追加 AUTOA 持续成功 0、KATUSDT 70% 平仓后出现首次开仓通知的现场；此前过早的“全部完成”已纠正，本次修复完成证据如下。
- AUTOA 现场已证实：日历和新浪实时行情正常，600185/000001 的东方财富历史日线均 `ConnectionError/RemoteDisconnected`，导致0根行情。新增同数据源内的腾讯 `qfqday` 备用后，即使东方财富仍断开，两只实际只读样本均返回20根、末根2026-09-09；不取未复权数据替代，不跳过无日历时的当日交易确认。扫描计数区分成功/规则跳过/无行情/待确认/失败。
- KATUSDT 只读订单证据：11:22 BUY35017、11:26 SELL24511、11:38 SELL7354，剩3152；12:18:15新脚本进程启动，12:27 BUY32635（at-客户端ID），核对时实际35787。确认遗留实际仓位被当OPEN；原始本地记录缺失时机无法从现存文件证明，未擅自回写风控元数据或撤销成交。已按用户纠正恢复启动/每日拉池时读取实际持仓，校正已登记均价/存在性并保留策略/tp_count/初始下轨；OPEN有实际同标的仓位拒绝，ADD无对应实际仓位取消并清理；不恢复15分钟同步、不补造N策略。
- 持久化修复：完整持仓/观察快照仅日报和退出；真实订单通过单标的pending/resolved增量恢复日志和快照序号恢复，AUTOA虚拟动作不逐笔写盘，旧虚拟pending取消后重新评估。明确拒单终结、未知真实订单保留补查；失败加/平仓继续原观察后处理。日志追加失败回滚，终态重试按订单ID防止重复应用和记录；Excel可选订单编号跨重启去重，未直接修改运行中的业务文件。
- 本轮新增失败回归先出现9项失败；独立R1又发现日志失败回滚/幂等、元数据失败阻断持仓核对、历史畸形响应不备用，R2仅剩畸形币安元数据问题；均补红色验证并修复。fresh reviewer `/root/review_trade_recovery_fix`，collaboration-optimize.spawn_agent、gpt-5.6-sol/high异构，无回退，同一session R3终态可合，全部旧finding resolved，无blocking/important/nit。
- 本轮最终冻结：入口 SHA256 `99618199C41042653F2CD7AF61E49201AE6505860FC160BD36EE996E489134C4`；测试 `EBCCC152AB6D42BA33BAACCA9C0AA6D0C0C1FC01C5A38587A2A7E1CBA463AF38`；Epic为frontmatter批准版本。新入口53项（含620组核心parity）通过；原入口/持仓/效率/A状态/回测/通知218项通过，回测381点无差异，30个原有策略规则方法AST与修复前完全相同。Ruff F、编译、diff检查、两种engine构造及拦截main的直接入口smoke通过。
- 结论归入 Epic DEC-16～19、新入口测试和本游标；临时 `issue-auto-trade-execution-recovery.md` 及系统Temp审查源码快照在交付时清理。不新增说明文档/lesson，不自动commit/push，未更改现有交易进程或真实订单。

- 2026-09-09 owner 接受第二阶段业务抽象，授权统一 MarketBars、决策/成交结果、业务状态及引擎/策略/执行器职责；单文件和全部已确认业务行为保持。执行前基线入口 SHA256 `FB71AA3C9F421032B73B46419D61E6506EC19FA88DA9FFE89BA494F59FE0AAF8`、测试 SHA256 `ACAEED5A94EC81D034EEC3210E2271DB2AFB6B6B7125EA360F57C2ACFF52257F`，临时快照在系统Temp的autotrade-domain-20260909-baseline.py及tests-baseline.py，交付前清理。
- 第二阶段实现草稿已经替换新入口：`TradingState` 是业务状态唯一写入者；`MarketBars` 是行情边界对象；`TradingEngine` 是扫描/日报/状态提交唯一编排者；`BinanceGateway`/`AshareMarketData` 是行情源；`BinanceExecutor`/`AshareExecutor` 是执行器；`AUTOBN`/`AUTOA` 只返回 `Decision`/`TradeIntent` 和市场规则。
- 第二阶段当前冻结：入口 SHA256 `D793A5208E799DFFF1C694B03BB8CF5DC8C07466190B2ACC3E8CC4224660C7AC`，测试 SHA256 `F38A5E90E79D5FFECC3FF4D7718859AD3F746D33927AD2C1D44BEE95988DC434`。订单客户端ID、`PENDING_ORDERS` 状态编解码和未知订单按ID补查已实现；positionSide隔离、状态提交前待确认落盘和成交后通知已补齐，审查目标现已停止移动。
- 交易未知结果使用 `PENDING_ORDERS` 运行状态：提交生成 client order id；异常后按 id 补查，未确认前不重提；确认成交后先提交状态/记录再通知。取消测试覆盖引擎状态边界。
- 当前第二阶段 smoke：新入口 py_compile/ruff F通过；原仓库旧测试246项通过（旧测试仍针对原入口）；新架构测试25项通过。新增订单待确认、状态Codec、positionSide隔离、统一行情、引擎顺序、状态先提交后通知和策略风控单位测试。ITEM-6/7/8实现完成；第二阶段本地回归、静态检查和结构自审通过。
- AST结构核验：AUTOA/AUTOBN类体不直接引用 `self.alert_all`、`self.records` 或 `self.state`；共享状态只在 `TradingEngine`/`TradingState`，执行器只返回结果，策略只返回 `Decision`/`TradeIntent`。

- 原文件基线：AUTOA 使用类级可变状态和大量 `@classmethod`；AUTOBN 使用实例状态和 `from_cfg()` 构造。
- 原文件基线：AUTOA 收盘池对已有标的刷新时间戳、对新标的追加观察，不删除未命中观察。
- 现有保存策略已提交并推送 `1375716b`；新重构文件已完成实现和回归，未纳入提交。
- 方案状态：第二阶段 owner 已授权实现；ITEM-6/7/8实现完成，本地回归和结构自审通过，等待用户使用验收或授权提交。
- 实现按用户“开始实现”持续推进；本轮仅授权实施，新代码不自动 commit/push。之前的推送授权仅适用于 `1375716b`。保留实现检查点到最终交付，不因未授权提交中断已经授权的实施。
- 设计审查 `/root/review_strategy_design`（collaboration-optimize.spawn_agent，gpt-5.6-sol/high，异构 reviewer）指出生命周期、合并和启动契约不够具体。已把会话确认的时序、合并规则和接口细节补回 Epic；不额外给原本无 BZ 的观察补标签。
- owner 追加纠正：策略专用账户不考虑手动开仓，取消定期持仓同步；每日报告只估值本地已登记的实际仓位，不补造 N 持仓。
- 新文件两个策略均为实例；状态、缓存、连接和锁隔离，记录管理器由主入口显式共用。没有向业务 JSON/Excel、真实行情、通知或交易接口写入。
- 初轮验证：`uv run --no-sync python -B -m unittest tokenDemo.test_autoTrade_pm_refactored` 21 项通过，包含 160 组 AUTOA 状态/通知对照、40 组 AUTOBN 状态/通知对照、150 组各市场指标精确对照；ruff F 通过。
- 扩充后新入口 26 项、仓库 tokenDemo 完整 247 项通过。46 个辅助方法经 AST 消除实例化/缓存字段改名后与旧实现相同；并发持仓检查、取消收尾、真实 Python 进程退出保存均有定向验证。
- 远端核验：`git -c http.sslBackend=openssl -c http.version=HTTP/1.1 -c http.lowSpeedLimit=1 -c http.lowSpeedTime=15 ls-remote --heads origin dev` 返回 `1375716b0a21160c9b3f5190b8b552c30e295751`，此前落盘调整已经推送，本重构未提交。
- 首轮 change review 目标：新入口 SHA256 `541963A88F74E1A0DBA4E8E07C1DB97B357094BD905974FC05A069FF2CFD7E08`；新测试 SHA256 `622751187940A3840624D11B47447D02C075331B97B19459BAFF9E7B21DD9C2D`。fresh reviewer `/root/review_strategy_code`，collaboration-optimize.spawn_agent，异构 gpt-5.6-sol/high。
- 首轮 change review 终态：通知等待未限时、启动无元数据时平仓 TypeError、上海业务时钟三个发现。已先新增 3 条失败验证（1 fail / 2 error）并修正，定向全部转绿；全平复用确认数量，缺精度部分平仓明确延后。其余策略/通知时序保持。
- contract review 第二轮通过：`/root/review_strategy_contract`，上一轮两项 important 均 resolved；无 blocking/important。批准语义及最新会话纠正见 Epic DEC-7～14。
- 最新验证：新入口 29 项、完整 250 项通过；基线指标脚本 381 点零差异。拦截 `asyncio.run` 的直接脚本入口检查通过，依赖和两种具体类均可加载，没有实盘启动。
- 第二轮 change review 冻结：入口 SHA256 `0B9E1A693980963B0A024C4F9072BE9BEB030C06B8533C268D25D0C7DD7886B9`，测试 SHA256 `23AFB1D50994E6EBB970662E66AB30EF27720F29C8C165D9046B1F0D9AA5D44B`，同一 reviewer lineage 已通过。
- 第二轮 change review 已通过（`/root/review_strategy_code`）：三项首轮发现 resolved，无 blocking/important/nit；reviewer 独立复跑新入口29项通过。实现及验证子项完成，进入最终验收阶段。
- 临时脚本 `C:/Users/dell/AppData/Local/Temp/autotrade-kernel-build.py` 与方法索引 `auto_methods.txt` 已清理。
- final acceptance：fresh reviewer `/root/accept_strategy_kernel`，collaboration-optimize.spawn_agent，异构 gpt-5.6-sol/high，冻结 Epic/入口/测试沿用上述最终哈希。终态通过，无 blocking/important/未完成项；独立重跑新入口29项、完整250项、ruff/编译、拦截main的入口smoke均通过，目标无漂移。
- 交付文件：`tokenDemo/autoTrade_pm_refactored.py`、`tokenDemo/test_autoTrade_pm_refactored.py`；沿用原业务JSON/Excel和已有通知模块。原入口保持 `1375716b` 内容，用户的业务Excel和其他issue游标未纳入本轮变更。
- 运行入口：`uv run python tokenDemo/autoTrade_pm_refactored.py`。没有启动实盘或更改已有运行进程；本重构不自动提交或推送。work保留至owner验收，契约主源为当前 Epic，不另建说明文档或lesson。
- 2026-09-09 owner 追加多仓止盈后价格保底，新增规则为 DEC-15，覆盖此前“仅 OI 止损/止损规则不变”口径；初始下轨固定，成功止盈后 `tp_count > 0` 且价格 `<= stop_loss` 全平，失败止盈不启用，OI 保留。旧持仓沿用已保存阈值，不回填历史下轨。
- 新规则验证：修改前新增10项中出现8个失败观察（含子案例），修复并补齐13项后，新入口42项全部通过；既有parity仅调整多仓固定下轨这一明确授权差异。真实全平调用/记录、OI、DCA、拒单、通知取消、重启和空仓均覆盖。
- 追加 change review：fresh reviewer `/root/review_bn_postprofit_stop`，collaboration-optimize.spawn_agent，异构 gpt-5.6-sol/high。冻结入口 SHA256 `FB71AA3C9F421032B73B46419D61E6506EC19FA88DA9FFE89BA494F59FE0AAF8`、测试 SHA256 `ACAEED5A94EC81D034EEC3210E2271DB2AFB6B6B7125EA360F57C2ACFF52257F`。终态通过，无 blocking/important/nit；reviewer 独立13项和ruff通过。
- 本次规则毕业到 Epic DEC-15，验证证据汇总本游标；临时功能游标 `feat-autobn-post-profit-stop.md` 与两份仓库外对照快照已清理。原入口未改，未触碰业务文件/实盘进程，不自动commit或push。

- 2026-09-10 本轮三源恢复与OI阈值max：按cs-issue推进。腾讯一次请求返回历史和当前OHLCV，成交量统一为手；东方财富池失败/空结果不清状态；新浪纯Python日历解析与既有参考全量8797日期一致。共用OI公式由min改max，新开多仓/缺失guard恢复/N恢复共用，已有有效guard不回算。旧min的新增回归实测失败110!=180；修复后新入口92项通过（包含既有核心规则对照和HTTP诊断测试），ruff F通过。三源公开只读验证得到20根策略日线、31个涨停标的、日历覆盖2026-12-31；未请求币安、未启动实盘或改业务文件。独立审查已完成；不commit/push。

- 本轮独立change review：collaboration reviewer `/root/review_three_source_max`（gpt-5.6-sol/high），首轮发现东方财富tc未校验，五类回归修前失败、修后通过；第二轮终态通过，无blocking/important/nit。最终93项测试、ruff F/编译/diff检查通过。冻结入口SHA256 `779BD10D7691596A44FBF8D6F87F1845BD5243FBF81F9D992AF88C7E3268CB6E`，测试 `5A5D200B7EA08ACF8405A743086D29A263CB091237084D778F27E215D264923A`，Epic `CA8FEBAEC7964B20EA7E99E8D5A178509AE45CB5FA12ED91556FA30314EB90A4`。结论归入DEC-20/21/23，临时任务基线目录已清理；既有请求诊断与业务文件保留，不重启、不commit/push。

- 2026-09-10 新阶段：用户要求建立AUTOBN slot WS行情work游标，方案主源为Epic DEC-24，推进入口为 `feat-autobn-slot-kline-ws.md`。状态ready，仅记录方案，未开始产品代码实现。

- 2026-09-10 slot WS官方SDK修复完成：详见 `feat-autobn-slot-kline-ws.md` 最终交付及Epic DEC-24；104tests/完整ruff/真实公开WS订退重连与REST历史缓存验证通过，独立R3可合。未提交推送或重启。

- 2026-09-10 DEC-25当前待处理slot集合完成：取消5秒及12秒限制、未完成跨轮保留、完成后退订，109tests/真实WS订阅状态验证及独立review通过；见feat-autobn-slot-kline-ws游标。未commit/push/重启。
