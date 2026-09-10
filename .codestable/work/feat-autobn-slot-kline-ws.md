---
status: complete
created: 2026-09-10
updated: 2026-09-10
type: feat
canonical: ../epics/auto-trade-strategy-kernel.md
---
# AUTOBN slot日K订阅与历史缓存

## 目标与授权

减少每次扫描重复拉30根日K的REST调用。用户已确认方案并要求“开始work游标”；本轮仅建立游标和同步canonical DEC-24，尚未实施。后续进入cs-feat；不可用的ultracode不伪称已调用。

## 当前事实与依据

- 入口 `tokenDemo/autoTrade_pm_refactored.py`：BinanceMarketData.fetch_bars 当前每标的REST interval=1d、limit=30；TradingEngine._scan按slot切片，process_instrument经共享并发/策略/执行链处理。
- 本会话读取日志：旧进程11:26:01至11:31:01滚动5分钟775次HTTP，其中K线724、OI35、多空比16；快照中1分钟最高182、5分钟最高832，未记录429/418。证明K线占大头，不证明历史429根因。
- 官方SDK核实K线流symbol@kline_1d、当前K更新、OHLCV及k.t/k.x字段；REST支持startTime/endTime/limit。正式容量等参数未完成当前核实。未经专门验证，不把临时订阅当成保证立即返回的查询接口。
- 当前工作树已有三源恢复、OI阈值max与Binance请求诊断等未提交改动，以及用户业务Excel/AGENTS等；后续基于现状增量修改，不回退或混入无关数据。

## 已确认方案

以Epic DEC-24为唯一契约主源：slot订阅，谁到谁并发检测，单标的每轮一次，整批统一退订；只常驻缓存29根已收盘日K；WS最新一根只保留本轮临时数据。无每日刷新标记，历史末根必须为有效WS开盘时间D前一天且29根完整连续，否则REST按[D-29天,D-1毫秒]、limit29刷新。跨日由同一缓存有效性规则自动触发。

## 实施顺序

- [x] 核实扫描/prepare/pending/信号和日报行情调用链，确定批次行情公开边界，保持AUTOA和共享交易主链。
- [x] 核实WS消息字段、动态订阅/退订和REST时间边界；未运行实盘，新增断连PushPlus通知代码但未触发真实通知。
- [x] 建立日期/缓存/批次并发的回归，并实施历史缓存、WS批次生命周期及行情就绪处理。
- [x] 运行核心规则同输入对照与故障测试；95项新入口测试通过，包含WS字段覆盖、重复消息替换、29根历史时间边界、既有策略对照。
- [ ] 用实际slot规模有界验证订阅/首消息/退订，保留REST与WS成本证据；当前未连接实盘WS。
- [ ] 并发、顺序和一致性语义改变，完成独立change review并处理发现；更新DEC-24实现状态及本游标证据。

## 验收与边界

- 首次启动仅为缓存无效的标的拉历史；同日下一slot不重复REST；跨UTC日自动刷新昨天最终OHLCV，无需收盘WS事件或每日刷新标记。
- REST末根日期/数量/连续性校验；不足29根、乱序重复、无效数值不得触发策略。覆盖UTC午夜（上海08:00）前后、REST途中跨日、旧WS消息和排队期间跨日。
- WS重复消息不重复检测；收到谁先处理谁；不同标的并发；一个标的无消息/失败不永久阻塞整批；取消、超时和断线都释放本轮订阅/任务。
- 同标的REST修复去重，保持已有并发约束；恢复不能制造全市场REST洪峰。检测使用固定30根快照。验证开平仓/DCA/guard与同输入旧规则一致，数据到达时序变化单独注明。
- 既有请求诊断覆盖新的REST调用；WS消息计数与HTTP调用分开，不以REST下降误报整体成本。临时观测如需新增，先按skill授权边界处理。
- 不改AUTOA三源、OI/多空比缓存、策略公式、订单/持仓提交与通知落盘，不改业务JSON/Excel，不提交/推送或重启进程。

## WS断连重连专项（用户追加重点）

- [ ] 单一连接管理者、心跳/读异常/关闭统一恢复，有上限指数退避加抖动；退出立即停止，不出现每标的重连风暴。
- [ ] 连接恢复后仅重订活跃批次未完成标的，回执与新有效行情分别确认；旧连接代次/迟到消息隔离，已检测或执行中的标的不重复触发。
- [ ] 批次超时预算跨重连共享；退订失败时正确关闭/释放失效连接；批次结束/程序退出后无幽灵订阅或后台重连。
- [ ] 覆盖订阅前断线、订阅确认前断线、部分标的就绪后断线、检测/订单执行中断线、退订中断线、多次失败与恢复、跨UTC日重连。
- [ ] 重连不清已收盘历史、不自动全市场REST补数；新WS日K按统一日期规则判定是否刷新。故障中不沿用旧临时行情，原pending订单恢复机制不变。
- [ ] 持续故障、无首消息、心跳失效有明确日志/扫描结果；持仓标的等待与失败可观测。正式心跳/连接寿命参数待核实，不写猜测值。

## 当前实现证据

- `BinanceMarketData` 新增单一WS后台循环：slot开始订阅、slot结束退订；当前K只存本轮临时消息，历史缓存只保留29根。断连采用1至30秒有界退避；恢复后自动重订活跃slot，退出取消后台任务。
- `TradingEngine._scan` 在TaskGroup前后调用begin_slot/end_slot，保持谁先有行情谁进入原process_instrument并发链；非WS或测试数据源按兼容空实现处理。`fetch_bars` 在slot内等待WS当前K，缓存失效时REST传start_time/end_time/limit=29。
- 断连通过一次性告警回调发送PushPlus `TradeNotification`；通知失败只记录日志，重连后清除告警标记。核心订单/pending链路未改。
- 新增WS字段覆盖、重复消息替换、29根历史时间边界测试；已有95项新入口回归通过，ruff F、编译和diff检查待最终运行。实现期间未请求Binance、未发通知/订单。

## 状态与下一步

实现中。模拟故障回归已完成；WS连接正式参数、真实断连恢复和实际slot吞吐仍待有界测试。PushPlus断连告警已接入，每次连续断连只通知一次，重连后复位；通知失败不影响行情/交易链路。不引入每日标记、当前日K长期缓存或全市场常驻订阅。


## 2026-09-10 实盘无消息后的修复（进行中，以此覆盖此前过早完成描述）

- 真实复现：旧 `wss://fstream.binance.com/ws` 收到SUBSCRIBE回执但多个流无行情；正确 `/market/ws` 可收到日K。原95项测试只证明旧规则与少量解析，不证明WS生命周期正确。此前“模拟故障回归已完成”不准确。
- 已安装官方SDK 13.0.0：连接支持market/public/private；高层subscribe(list)逐币sleep0.5秒，unsubscribe(list)逐币重复发送整批。采用SDK子类BinanceKlineStream通过公开connect/send_message/receive_loop/close能力适配批量订退与回执，不使用其全局订阅映射或高层逐币路径。不改依赖版本。
- 修复：移除手写aiohttp连接和http参数控制的隐藏开关；BN无有效WS就无行情，取消REST30回退。wait_ready移至交易信号量外，全部标的共享首消息截止；slot setup位于finally保护内。ACK后才接受当前连接代次消息，UTC日/OHLCV/事件时间校验，REST后和策略开始前重核对。检测开始就移出重订集合。断线清空临时行情，不清历史；统一抖动退避、回执心跳、SDK23小时轮换、后台任务关闭；PushPlus一次故障一次通知，行情恢复后复位。
- 真实时钟差约2.1秒：将事件时效允许偏差设为正负5秒，仍严格核对UTC日开盘时间；没有放开跨日边界。
- 新增测试覆盖失效日期/数值/旧代次、无消息不REST、取消传播、历史跨日/断线、通知去重、退订失败关闭、本地真实SDK批量订退、回执超时、160等待者共享截止、重连仅未完成标的。104项通过，ruff F/compile/diff通过。
- 真实只读SDK：BTC/ETH 2.29秒均ready；LIST_SUBSCRIPTIONS核对订阅与退订为空；下一批复用；主动关闭本次测试socket后恢复；close后背景任务为0。BTC真实REST明确区间29根+WS形成30根，末两日时间1788912000000/1788998400000；再次fetch仍仅1次REST。没有使用账户密钥、交易/通知副作用或干预用户进程。
- AST证据：AUTOA/AUTOBN/TradingState/BinanceExecutor相对修复前完全一致。第二轮review沿用 `/root/review_slot_ws`：发现并修复回调generation晚绑定和E741变量名问题，新增旧连接回调拒绝测试；最终入口/测试哈希待复审确认。当前任务基线Temp/autotrade-ws-fix-02gd43x2收尾清理。

- 最终修复增量：lambda默认参数固定连接generation；真实mock连接重连后调用旧callback不更新、新callback更新，覆盖闭包晚绑定。完整ruff通过（不是仅F），104项tests及compile/diff通过。真实160symbol批次订阅160/12秒ready107无行情53/退订后空列表/背景0。R3冻结入口0015ED015CEA153656620F835317EA76C088707745DA458FCB82E356EA9F3C3B，测试94C0866AEF6A7F3F5882806615A624DE28D1B7A9C9649305EC8D13CF7A3F61F5；等待同reviewer终态，未提交/推送/重启。


## 最终交付状态（2026-09-10）

R3独立review `/root/review_slot_ws`（gpt-5.6-sol/high）终态可合，blocking/important/nit均清零；最终冻结代码/测试哈希与上述R3一致。104项测试、完整ruff、编译、diff检查通过。真实公开WS与REST小样本、160标的批次及主动断线恢复均验证完成，53/160首消息未就绪的实际限制已记录。产品代码实现完成，不保证免费公网链路长期无故障；未发送真实通知/订单，未重启、提交或推送。结论毕业到Epic DEC-24及对应测试，本游标按用户明确要求保留；临时基线目录autotrade-ws-fix-02gd43x2已清理。此前标为进行中的条目和初版实现证据仅为历史记录，以本节及DEC-24 SDK修复收敛为准。

## 2026-09-10 owner确认替代方案

通过cs-feat继续：一个当前待处理slot标的集合跨轮保留；本轮新标的加入去重，完成检测（含无信号）移除并批量退订，暂时失败/未收到行情留到下轮。历史不足单独结束本次尝试，下次自然调度再试。取消5秒消息年龄阈值，保持UTC日、字段、顺序、旧连接隔离；断线清快照，不清历史或待处理集合。此前不退订草稿与固定slot退订均由此替代，尚未验收，不启动实盘、不发通知/订单、不提交推送。

- 本轮最新纠正：取消12秒独立首消息预算，等待仅用本轮slot截止；取消5秒年龄限制。完成检测才移除并批量退订，未完成跨轮保留；begin_slot返回并集；真实短历史用InsufficientKlineHistory明确跳过、暂时失败保留。方案主源DEC-25，覆盖此前不退订草稿与DEC-24固定整批退订规则。
- 新增红色验证（60秒前当前日快照被拒绝）修后转绿，109项测试、完整ruff通过；含并集、仅完成退订、跨slot消息、旧回调、断线恢复未完成、取消保留、返回状态分类、短历史区别、单一截止。源码冻结前准备独立review；任务前备份Temp/autotrade-pending-slot-bi4doym7收尾删除。

- 真实只读验证：batch1 BTC/ETH均ready，只完成BTC后end_slot服务端LIST仅ETH；batch2仅新加BTC，begin_slot返回BTC+ETH，ETH即时ready；两币完成后LIST为空；close背景任务0。未跑策略/订单/通知。AST相对本轮前AUTOA/AUTOBN/TradingState/BinanceExecutor/BinanceKlineStream完全一致。等待fresh review `/root/review_pending_slots`（gpt-5.6-sol/high）终态；冻结入口9D0F942D77113D9624E580B3202C5A638075782BB4656BC47DF1762F30E579E0，测试7E3B19498E3A51E56DB4D4AD44E76924CF8E5C5353B35FC75B6876BBDA9476E5，Epic C4185AF77FC1DE34B13FB30107704B032441801F9AA5AF4866670FB750DAD6CE。

- DEC-25阶段最终验收：fresh `/root/review_pending_slots`（gpt-5.6-sol/high）终态可合，无blocking/important/nit，冻结三文件哈希一致。109tests、完整ruff/compile/diff检查及真实只读跨slot订退生命周期通过。结论归入Epic DEC-25与测试；work按用户要求保留。本次临时基线目录autotrade-pending-slot-bi4doym7已清理，未提交/推送或重启实盘。

## 2026-09-10 移除额外WS探测（cs-feat）

用户确认仅依赖SDK Ping/Pong维护连接，移除每20秒LIST_SUBSCRIPTIONS主动探测。接收结束/异常/轮换事件仍触发原重连，订退回执、取消清理、PushPlus通知保持。无静默断网主动探测承诺。沿用本work记录，不改交易规则，不自动提交推送或重启。验证使用既有SDK生命周期与重连测试、完整ruff/编译。

- 移除探测验证完成：既有16项WS专项测试通过（含SDK回执、连接恢复、旧回调隔离、取消与退出），完整ruff与编译/diff检查通过。仅删除周期控制请求及其等待分支，保留业务同步与订阅协议，不新增独立review阶段。未发送真实通知或订单，未commit/push/重启。

## 2026-09-10 WS简化与退避修复

用户授权优化审查发现：删除未使用slot计数、重复claim_bar、每标的历史锁，缓存命中只比较历史末根日期，REST新结果仍完整校验。复用现有单轮锁及去重任务边界；退避在收到有效恢复行情后归零，连续失败仍指数抖动。按cs-refactor收敛冗余，cs-issue处理退避恢复错误；不改策略、持久化、通知规则，不提交推送或重启。

- WS简化验证：新增两条回归修前均失败，修后111项全通过；完整ruff/compile/diff通过；AST核对AUTOA/AUTOBN/TradingState/BinanceExecutor/BinanceKlineStream相对本次前完全相同。任务前Temp/autotrade-ws-simplify-w1lerkez收尾清理；独立review `/root/review_ws_simplify`（gpt-5.6-sol/high）审阅冻结入口1DB2E47566179E4B57B2BC410FDDE8DD147B354725D1640E727792145DD0D690、测试D5F64EAEF17DA249FE78A2187B9E4D73B2CE65299A92338086FB01C661CD94FE，等待终态。

- WS简化最终验收：`/root/review_ws_simplify`终态通过，无blocking/important/nit；独立核对生产单币串行、去重和返回到策略之间无await、历史唯一校验写入及退避恢复，另跑4项定向通过，冻结hash无漂移。111tests、完整ruff/compile/diff通过。结论归入Epic与测试，临时基线已清理；未commit/push或重启，保留用户业务Excel与AGENTS。
