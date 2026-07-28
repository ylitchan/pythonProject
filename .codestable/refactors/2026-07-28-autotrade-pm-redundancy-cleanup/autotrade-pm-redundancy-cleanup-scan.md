---
doc_type: refactor-scan
refactor: 2026-07-28-autotrade-pm-redundancy-cleanup
status: pending-user-selection
scope: tokenDemo/autoTrade_pm.py 单文件（3682 行，含 AUTOBN :294-2411 / AUTOA :2412-3554），候选来源为已完成的 cs-audit `2026-07-28-autotrade-pm-redundancy` 17 条发现
summary: 18 条，结构 4 / 性能 5 / 可读性 9；风险 低 9 / 中 8 / 高 1
---

# autotrade-pm-redundancy-cleanup scan

## 总览

- **扫描范围**：`tokenDemo/autoTrade_pm.py`（唯一改动文件）+ `tokenDemo/test_autoTrade_pm.py`（只读，用于判定测试覆盖）
- **候选来源**：不是本轮新扫的。17 条全部来自 `.codestable/audits/2026-07-28-autotrade-pm-redundancy`，行号与核心论断在 audit 阶段已逐条手工复核。本轮 scan 做的是**重构可行性复核**：每条重新确认①改动是否行为等价②测试覆盖够不够③调用点形态（有没有位置传参陷阱）。
- **发现 18 条**：结构 4（#01 #06 #07 #17）/ 性能 5（#04 #09 #11 #12 #16）/ 可读性 9（#02 #03 #05 #08 #10 #13 #14 #15 #18）
- **按风险**：低 9（#02 #03 #08 #10 #12 #13 #14 #15 #17）/ 中 8（#01 #04 #05 #07 #09 #11 #16 #18）/ 高 1（#06）
- **建议先做**：#03 #14 #17 #07+#18 —— 先清零引用配置与收紧两套通知签名，再处理已确认需要接线的 #08
- **建议慎做 / 后做**：
  - **#04 + #05 必须合并成一步**（同一段代码的两个侧面，单侧改动会让"推送的止盈止损"与"实际挂单的止盈止损"从恒等变成两条独立路径）
  - **#09 需要前置刻画测试**（`calculate_chebyshev_probability` 现有测试全是 `MagicMock` 替身，函数体本身零覆盖）
  - **#06 排最后**（改动面最大，且必须等 #04+#05 把死分支清掉，否则会把冗余一起抽进公共函数）
  - **#16 置信度 medium**（audit 原判），是唯一一条改完后"某条路径上多算一次纯算术"的条目
- **前置检查 7 条**：**6 条通过，第 6 条（范围太大）按行数字面命中，已在下节交代并给出两种处置**

---

## 前置检查交代

| # | 检查项 | 结论 | 依据 |
|---|---|---|---|
| 1 | 夹带行为改动 | **通过（有 2 处刻意规避）** | 见下方"两处刻意偏离 audit 建议" |
| 2 | 测试覆盖 | **通过（1 条需前置补测）** | 全量 114 个用例基线已跑通（1.842s，OK）。逐条查引用：`close_bn_position` 29 次、`open_bn_position` 17、`rzq_token` 15、`calculate_atr` 14、`check_side` 12、`_is_bd_observation` 11、`send_msg` 24、`stock_zh_a_hist` 8。**两处缺口**：`from_cfg` 零引用（#03/#07/#14 靠 grep 自证，不依赖测试）、`calculate_chebyshev_probability` 只被 mock 替身（#09 前置补刻画测试） |
| 3 | 跨模块 | 通过 | 单文件。`autoTrade.py` / `autoTrade_papi.py` / `autoBN_v2.py` 有同源副本但各自独立，本轮不碰（跨文件三副本重复需单独立项） |
| 4 | 风格口味 | 通过 | 17 条无一条是命名 / 引号 / 顺序类。每条的"问题"字段都落到可数指标（重复次数 / 引用数 / 不可达证明） |
| 5 | 生成产物或第三方 | 通过 | 目标文件是手写业务代码，非生成物 |
| 6 | 范围太大 | **字面命中，见下** | 文件 3682 行 > 阈值 3000 |
| 7 | 扫完没东西可改 | 通过 | 17 条 |

### 第 6 条的诚实处置

按字面口径**命中**：单文件 3682 行超过 3000 行阈值。不打算糊过去，所以把这条检查真正要防的失败模式和本轮实情摆一起：

| 该检查要防的 | 本轮实情 |
|---|---|
| 产出没法决策的长清单 | 清单 17 条 < 20 候选阈值，且每条已在 audit 阶段经"抹掉它有没有执行路径会变"+"引用的代码在那一行真的存在吗"两个对抗视角过筛（45 条候选被否掉） |
| 改动面吞掉上下文 | 实际触碰约 **250 行 / 1 文件**，不是 3682 行。最大单条（#06）约 60 行 |
| 改到后面忘了前面的约束 | 拆 3 批，每批 ≤ 7 条，批间可独立提交与回滚 |

**两种处置，请你选**：

- **A（默认，本方案按此写）**：单个 refactor 立项，3 批推进，批间硬 checkpoint。理由是 17 条互相之间有真实依赖（#04+#05 → #06；死分支先清才好抽函数），拆成 3 个立项会把依赖关系切断在文档之间。
- **B（严格合规）**：拆成 3 个独立 refactor 立项，批次边界即立项边界（现有分批切口本来就干净）。代价是 3 套 scan/design/checklist 文档，以及 #06 的前置依赖要跨立项引用。

### 两处刻意偏离 audit 建议（防止夹带行为改动）

audit 给的是"发现 + 建议"，其中两条建议若照做会越出重构边界，本方案改了处置：

1. **#08 的 BD 窗口常量：按用户确认改为真实接线，但拆分量窗口与 OI 窗口。**
   复用已有 `KLINE_LIMIT = 30`（BZ/BD 共用的日 K 数据量口径）与 `OI_QUERY_LIMIT = 30`；删除五枚失联旧常量，新建 `BD_VOLUME_LOOKBACK_COUNT = 10`、`BD_VOLUME_RECENT_COUNT = 3`、`BD_OI_LOOKBACK_COUNT = 10`、`BD_OI_RECENT_COUNT = 3`，分别替换 `:1894-1901` 的字面量。`:1884` 只检查 `kline_close` 长度：`kline_close` 与 `kline_volume` 均由同一个 `kline` 同步推导，长度恒等，双判是冗余。默认值复制当前真实值，行为不变。
2. **#17 的兜底分支：audit 给"删兜底 / 补 `_unwrap_api_response`"二选一，本方案锁定"删"。**
   补拆包是修一条不可达的错代码 = 修 bug，属 `cs-issue` 范畴；删不可达分支是行为等价。重构里不偷偷修 bug。

---

## 附录先行：本轮新增的两个方法号

方法库（`reference/methods.md`）L2 层没有"删死代码"和"删恒真/恒假条件"这两个动作，而本轮 17 条里 9 条落在这两个动作上。按方法库自己的扩展规则（层内编号递增、字段填齐）补两条，供下方条目引用。**这两条只写在本 scan 里，未写入全局方法库**——是否上收由你定。

### M-L2-09 Remove Redundant Conditional 删除冗余条件

- **适用**：某个 `if` / `elif` 的条件在其所有可达前驱上恒真或恒假（可由前置守卫、初始化值、赋值点集合静态证明）
- **不适用**：条件只是"目前没见过为假"（协议漂移防护、外部输入校验）——那是防御性代码，不是冗余
- **步骤**：
  1. 列出该条件所依赖变量的**全部**写入点（grep 变量名，不漏 `+=` / 解包 / 属性赋值）
  2. 证明恒真 / 恒假：对每条可达路径给出取值
  3. 恒真 → 去掉 `if` 保留分支体；恒假 → 连同分支体一并删；两分支相同 → 合并
  4. 跑测试
- **风险点**：漏掉写入点（尤其是循环回边、异常路径、并发共享对象）；把"防御"误判为"冗余"
- **验证**：跑覆盖该函数的单元测试；补一条断言原分支内的行为仍成立
- **前后端**：通用
- **配哪种 scan 项**：恒真守卫 / 不可达 else / 两分支体完全相同

### M-L2-10 Remove Dead Code 删除死代码

- **适用**：零引用的常量 / 字段 / 形参 / 返回字段，或静态可证明不可达的分支
- **不适用**：被反射、动态 `getattr`、序列化、外部调用方引用（本文件所有目标均为实例私有，已确认无外部引用方）
- **步骤**：
  1. grep 全项目（含测试）确认零引用；**若删的是形参，必须按调用点的位置/关键字形态逐个核对**（见风险点）
  2. 一次只删一个概念，删完立刻跑测试
  3. 连带清理注释残留、`from_cfg` 注入、环境变量文档
  4. grep 复查零残留
- **风险点**：**本项目有真实事故先例**——`2026-07-25-auto-trade-dead-code` 删 `stock_zh_a_hist` 的 `fields` 形参前断言"所有调用方均未传入"，但 4 个调用点是**位置传参**，删后该字符串静默绑到 `start_date`，AUTOA 全部日线路径失败。故删形参时 grep 文本不够，必须枚举调用点的实参形态（AST 或逐个打开）
- **验证**：全量测试 + `grep` 零引用 + 形参类改动附调用点形态清单
- **前后端**：通用
- **配哪种 scan 项**：零引用常量 / 字段 / 形参、不可达兜底分支、无人消费的返回字段

---

## 条目

> 勾选方式：在标题行末尾标 `✓` 或 `✗`（`✗` 后面跟一行理由）。

### [01] 抽 `_clear_closed_position` 收拢三处平仓清理块

- **位置**：`tokenDemo/autoTrade_pm.py:893-897`、`:965-969`、`:999-1003`
- **分类**：结构
- **现状**：`close_bn_position` 三条平仓路径各抄一份同样两步：
  ```python
  self._handle_closed_position_observation(symbol, close_info, time.time())
  if symbol in self.alert_all["POSITIONS"]:
      self.alert_all["POSITIONS"].pop(symbol)
  ```
- **问题**：同一段 3 行代码逐字重复 3 次（amount==0 预检退出 / 平仓后 remaining==0 / 异常后重查确认为 0）。三处必须同步演进但没有任何机制保证——`_handle_closed_position_observation` 的签名或 `POSITIONS` 的清理口径任一变化都要改 3 个地方
- **建议**：抽 `_clear_closed_position(self, symbol, close_info)`，函数体内保留 `time.time()` 调用与 `if symbol in ... : pop` 原样（**不**顺手换成 `pop(symbol, None)`，那是另一条），三个调用点收成单行
- **建议映射的方法**：M-L2-01 Extract Function
- **风险**：中（落在真实平仓控制流上；但三条路径各有测试：A 路径 `get_amount_close` 返回 `(0,0)` 共 4 例，B 路径 `side_effect=[(10,10),(0,0)]` 共 2 例，C 路径异常后重查 2 例）
- **验证**：AI 自证（`uv run python -m unittest tokenDemo.test_autoTrade_pm -q`，114 例全绿；额外确认 `time.time` 的 patch 目标是模块级 `tokenDemo.autoTrade_pm.time.time`，移进 helper 后 patch 仍生效，且每条路径的 `time.time()` 调用次数保持 1 次不变）
- **范围**：约 15 行 / 1 文件

### [02] 删 DCA 开仓失败分支里恒真的 strategy 回滚守卫

- **位置**：`tokenDemo/autoTrade_pm.py:1617-1620`（多头）、`:1736-1739`（空头）
- **分类**：可读性
- **现状**：`:1587` 先 `close_info.strategy.append(PositionSide.DCA)`，开仓失败后回滚时又判一次：
  ```python
  if close_info.strategy and close_info.strategy[-1] == PositionSide.DCA:
      close_info.strategy.pop()
  ```
- **问题**：条件恒真。全文件 `close_info.strategy` 的写入点只有 4 处（`:1587` `:1621` `:1706` `:1740`，AUTOA 侧 `:3087` 是另一个对象），append 与该守卫之间唯一的调用是 `open_bn_position`（`:723`），已确认它不触碰 `strategy`；每次 `rzq_token` 用 `Position.model_validate` 新建 `close_info`（`:1925-1927`），不存在跨协程共享。守卫的两个子条件在此处都不可能为假
- **建议**：两处均改为无条件 `close_info.strategy.pop()`，紧跟一行注释说明"与 `:1587` 的 append 配对"
- **建议映射的方法**：M-L2-09 Remove Redundant Conditional
- **风险**：低（局部 2 行；`_manage_long_position` / `_manage_short_position` 各有 3 个用例覆盖）
- **验证**：AI 自证（全量 114 例；另 grep `close_info.strategy` 复核写入点仍为 4 处）
- **范围**：约 8 行 / 1 文件

### [03] 删 `from_cfg` 的 `margin_mode` 解析与赋值

- **位置**：`tokenDemo/autoTrade_pm.py:409-426`
- **分类**：可读性
- **现状**：`from_cfg` 读 `margin_mode` / `position_mode` 两个键，经一张 8 项映射表规范化后写入 `obj.margin_mode`
- **问题**：`margin_mode` 全文件零读取方（统一账户 PM 迁移后逐仓/全仓由账户级设置决定，下单不再带该参数）。18 行代码 + 一张映射表构成"假可配"：运维看到 `margin_mode` 键会以为能切逐仓
- **建议**：删 `:409-426` 整段（含 `margin_mode_raw`、`margin_mode_map`、`obj.margin_mode` 赋值），同步删 `:393-397` 注释里的 `margin_mode/position_mode` 两个键名
- **建议映射的方法**：M-L2-10 Remove Dead Code
- **风险**：低（`obj.margin_mode` 在 `autoTrade_pm.py` 与 `test_autoTrade_pm.py` 均零引用）
- **验证**：AI 自证（grep `margin_mode` / `position_mode` 全项目零残留；全量 114 例）
- **范围**：约 20 行 / 1 文件

### [04] `should_open` 段复用已算出的 `zy_msg` / `zs_msg`，删二次 `calc_stop_profit_loss`

- **位置**：`tokenDemo/autoTrade_pm.py:2065-2067`（消费侧）；来源 `:1989-1993`（多头）/ `:2031-2035`（空头）
- **分类**：性能
- **现状**：多头段与空头段各算过一次 `zy_msg, zs_msg = self.calc_stop_profit_loss(hl2, is_long=..., atr=atr_value)`；`if should_open:` 段用同样的三个入参再算一次得 `zy, zs`
- **问题**：`calc_stop_profit_loss`（`:1410-1420`）是纯函数（只读 `price` / `is_long` / `atr` 与类常量）。三个入参在两次调用之间无变化（`hl2` / `atr_value` 的唯一中间写入点是 `:2061-2064`，而该段不可达，见 #05；`is_long` 由 `open_info.side` 推出，而 `side` 与 `should_open=True` 同点置位）。于是**推送消息用的止盈止损（`zy_msg`/`zs_msg`，`:2006` `:2010`）与实际挂单用的（`zy`/`zs`，`:2074` 起）是两条独立计算路径**，今天恒等，任一侧改动即静默分叉
- **建议**：删 `:2065-2067`，`open_bn_position` 直接吃 `zy_msg` / `zs_msg`；**与 #05 合并为同一步执行**
- **建议映射的方法**：M-L2-03 Replace Temp with Query（复用既有计算结果，消除第二条来源）
- **风险**：中（改的是下单参数的取值来源。`rzq_token` 有 15 个用例，多头/空头信号各有专门测试类 `AutoBNLongSignalTest` / `AutoBNShortSignalTest`）
- **验证**：AI 自证（全量 114 例；额外断言 `open_bn_position` 收到的 `zy`/`zs` 与推送消息里的数值一致）+ **HUMAN**（批次完成后看一轮真实开仓推送，确认消息里的止盈止损与交易所挂单一致）
- **范围**：约 6 行 / 1 文件

### [05] 删 `should_open` 段的 `atr/hl2` 死兜底与死早退

- **位置**：`tokenDemo/autoTrade_pm.py:2061-2064`（兜底）、`:2068-2069`（早退）
- **分类**：可读性
- **现状**：
  ```python
  if atr_value is None or hl2 is None:   # :2061
      hl2 = (kline[-1][2] + kline[-1][3]) / 2
      atr_value = self.calculate_atr(kline)
  zy, zs = self.calc_stop_profit_loss(hl2, is_long=is_long, atr=atr_value)
  if zy == 0 and zs == 0:                # :2068
      return
  ```
- **问题**：`:2061` 恒假 → `:2062-2064` 不可达（含一次多余的 `calculate_atr` 调用）。证明：`:1965-1967` 初始化 `should_open=False` / `atr_value=None` / `hl2=None`，而 `should_open=True` 只在 `:2013` 与 `:2055` 置位，两处都严格晚于同段内 `hl2`、`atr_value` 的赋值——进入 `if should_open:` 时二者必非 `None`。`:2068` 同理不可达：`zy==0 and zs==0` 只在 `atr <= 0` 时发生，而 `atr<=0` 时上游 `:1996` / `:2038` 的 `if not (zy_msg == 0 and zs_msg == 0)` 就不会让 `should_open` 置真
- **建议**：删 `:2061-2064` 与 `:2068-2069`；**与 #04 合并为同一步执行**（同一段代码的两个侧面，audit 明确要求一次改完）
- **建议映射的方法**：M-L2-10 Remove Dead Code + M-L2-09 Remove Redundant Conditional
- **风险**：中（同 #04，与其共享验证）
- **验证**：AI 自证（同 #04；另 grep 确认 `atr_value` / `hl2` 在 `rzq_token` 内的写入点删后只剩两个信号段）
- **范围**：约 9 行 / 1 文件

### [06] 抽多空开仓观察块，消除两段近逐行复制

- **位置**：`tokenDemo/autoTrade_pm.py:1985-2013`（多头）、`:2027-2055`（空头）
- **分类**：结构
- **现状**：两段各 29 行，结构逐行对应，实质差异仅 4 处：`is_long=True/False`、`basis_rate < -THRESHOLD` vs `> THRESHOLD`、`long_lsr` vs `short_lsr`、`OrderSide.BUY` vs `SELL`。每段内部还各把同一条 `send_msg` f-string 写了两遍（一次带 `qy_key=self.signal_qy_key`，一次不带）
- **问题**：29 行 × 2 段重复，差异率 4/29 ≈ 14%；段内 f-string 再各重复 1 次（共 4 份同文本）。任何开仓信号口径调整都要改 2 处 + 4 份文案
- **建议**：抽 `_build_open_signal(self, symbol, kline, is_long, lsr, basis_rate)`，返回 `(hl2, atr_value, zy_msg, zs_msg)` 或 `None`（不满足则返回 `None`）；把段内 `if not (zy_msg == 0 and zs_msg == 0):` 反转为守卫子句提前 return；两份 `send_msg` 收成一次调用 + 一个 `qy_key` 变量。**必须在 #04+#05 完成后执行**，否则会把死分支一起抽进公共函数
- **建议映射的方法**：M-L2-01 Extract Function（配合 M-L2-08 Guard Clauses 处理段内条件）
- **风险**：**高**（本轮改动面最大的一条，落在开仓主路径；抽出的函数需返回 4 个值供调用方下单使用）
- **验证**：AI 自证（全量 114 例，重点 `AutoBNLongSignalTest` / `AutoBNShortSignalTest`；逐字符 diff 两段推送文案确认渲染结果不变）+ **HUMAN**（各看一次真实多头、空头开仓推送）
- **范围**：约 60 行 / 1 文件

### [07] 删 `send_msg` 的 `wx` 形参与 `if wx:` 整段，`qy_key` 收为仅关键字

- **位置**：`tokenDemo/autoTrade_pm.py:429-434`（配置注入）、`:601-603`（签名）、`:628-642`（分支）、`:393-397`（注释残留）
- **分类**：结构
- **现状**：`send_msg(self, msg, wx=False, qy_key=None)` 的 `if wx:` 分支走内网 `wechatpadpro:1238`，读 `self.wx_key` / `self.user_name`；这两个字段只由 `from_cfg` 注入、只被该分支读取
- **问题**：24 个 AUTOBN 调用点**无一传 `wx=True`**（AST 枚举实参形态：22 处仅 1 个位置参，2 处为 `(msg, qy_key=...)`，位置参个数全为 1），测试文件零引用 `wx=True` / `wx_key` / `user_name`。整条个人微信通知链路（形参 + 2 字段 + 2 环境变量 `WX_KEY`/`USER_NAME` + 1 硬编码内网地址 + 1 形如真 key 的 UUID 默认值）从未执行
- **建议**：删 `wx` 形参与 `if wx:` 分支（`else` 体上提），删 `obj.wx_key` / `obj.user_name` 与注释残留；签名改 `async def send_msg(self, msg: str, *, qy_key: Optional[str] = None)`——加 `*` 是零成本的：AST 已证 24 处全部用 `qy_key=` 关键字形态，加了之后**永久杜绝 `fields` 那类位置传参错绑事故**
- **建议映射的方法**：M-L2-10 Remove Dead Code + M-L1-01 Parallel Change（签名变更走调用点枚举）
- **风险**：中（改公开签名。风险不来自技术难度，来自本项目已有的同类事故先例，故强制走 AST 枚举而非文本 grep）
- **验证**：AI 自证（附 24 个调用点实参形态清单；grep `wx_key` / `user_name` / `WX_KEY` / `USER_NAME` / `wechatpadpro` 全项目零残留；全量 114 例，`send_msg` 有 24 处测试引用）
- **范围**：约 30 行 / 1 文件

### [08] 删除失联旧常量并接线四枚独立 BD 窗口常量

- **位置**：`tokenDemo/autoTrade_pm.py:308`、`:314`、`:327`、`:343-344`、`:1884-1901`
- **分类**：可读性
- **现状**：五枚旧常量零引用，真正生效的是 `_is_bd_observation` 中的 `30 / 10 / 3` 字面量；K 线长度又已由 `rzq_token` 的 `KLINE_LIMIT` 入口守卫保证
- **问题**：旧常量是假配置；成交量与 OI 窗口虽然目前同为 10/3，却是两个应能独立调整的概念；`kline_close` 与 `kline_volume` 都由已通过入口守卫的同一个 `kline` 推导，内部长度双判整体不可达
- **建议**：删除五枚旧常量；复用 `KLINE_LIMIT` / `OI_QUERY_LIMIT`；新增并接线 `BD_VOLUME_LOOKBACK_COUNT/RECENT_COUNT` 与 `BD_OI_LOOKBACK_COUNT/RECENT_COUNT`，默认保持 10/3；删除 `_is_bd_observation` 的 K 线长度重复守卫
- **建议映射的方法**：M-L2-10 Remove Dead Code + M-L2-03 Extract Variable
- **风险**：中（默认值保持原字面量，行为等价；新增测试约束 recent < lookback 且窗口不超过数据查询量）
- **验证**：AI 自证（常量关系测试 + `_is_bd_observation` 既有用例 + 全量测试）
- **范围**：约 20 行 / 1 文件

### [09] 删切比雪夫返回值里无人消费的 `message` 构造

- **位置**：`tokenDemo/autoTrade_pm.py:1464`、`:1486`、`:1511-1523`
- **分类**：性能
- **现状**：`calculate_chebyshev_probability` 在三个出口各构造一段中文 `message`（正常出口是一组 `if k <= 1 / else` 的长 f-string）
- **问题**：三个消费者全部只下标 `["chebyshev_upper_bound"]` 一个键——`:1212`（`check_side` LONG）、`:1910`（`_is_bd_observation`）、`:3292`（AUTOA）。`message` 零消费，每次调用白构造一次 f-string，正常出口还多一次 `k <= 1` 分支判断
- **建议**：删三处 `result["message"] = ...` 与正常出口那组仅服务于文案的 `if k <= 1 / else`（`:1512-1523`）。**保留** `:1494-1500` 那组 `if k <= 1 / else`——它算的是被消费的 `chebyshev_upper_bound`。其余字段（`mean` / `std` / `k` / `deviation` / `min_probability_in_range`）本轮不动
- **建议映射的方法**：M-L2-10 Remove Dead Code
- **风险**：中（**唯一测试覆盖缺口**：`test_autoTrade_pm.py:1942` 把该方法整体替换为 `MagicMock`，函数体零覆盖。且严格说删 f-string 会消掉一条潜在异常路径——若 `value` 不可 `:.4f` 格式化，今天会抛异常，删后不抛。实参均为 float，实际不可达，但需明说）
- **建议前置**：先补刻画测试（M-L1-04）固化 `chebyshev_upper_bound` 在 k≤1 / k>1 / std==0 / 单元素 四种输入下的取值，再动手
- **验证**：AI 自证（新增刻画测试通过；grep `["message"]` / `.get("message")` 在 AUTOBN 侧零消费；全量 114 例 + 新增用例）
- **范围**：约 20 行 / 1 文件（含前置测试约 30 行）

### [10] 删 SHORT 分支对 `completed_oi` 的二次判空

- **位置**：`tokenDemo/autoTrade_pm.py:1143-1144`
- **分类**：可读性
- **现状**：`if realtime_oi is None or completed_oi is None: return False, None, None`
- **问题**：多出的 `or` 分支恒与前一半同真假——`_get_bd_oi_windows` 只有"两个都有值"或"两个都是 `None`"两种返回形态，不存在一个为 `None` 另一个有值。多一个 `or` 让读者以为存在半失败态需要分别处理
- **建议**：收成 `if realtime_oi is None:`（保留对 `_get_bd_oi_windows` 返回契约的一次校验），并在该行加一句注释点明"两值同生同灭"
- **建议映射的方法**：M-L2-09 Remove Redundant Conditional
- **风险**：低（`check_side` 12 个用例、`_get_bd_oi_windows` 4 个用例覆盖）
- **验证**：AI 自证（全量 114 例；另读 `_get_bd_oi_windows` 全部 return 语句复核"同生同灭"）
- **范围**：约 3 行 / 1 文件

### [11] `stock_zh_a_hist` 保留原始 DataFrame 供 `tot_v` 取用，去掉第二次构建

- **位置**：`tokenDemo/autoTrade_pm.py:2980`、`:2991`
- **分类**：性能
- **现状**：`:2980` `hist_today = pd.DataFrame(res)`；`:2987` `hist_today = hist_today[required_columns].copy()` 把列裁到 `["m","v","p","avg_p"]`（**丢掉 `tot_v`**）；`:2991` 又 `pd.DataFrame(res).get("tot_v")` 把丢掉的列取回来
- **问题**：同一个 `res` 被构建成 DataFrame 两次。第二次不是笔误而是**为找回 `:2987` 裁掉的列**——分钟级数据每轮每只标的多一次全量 DataFrame 构建
- **建议**：`:2980` 起改为 `raw = pd.DataFrame(res)`，`hist_today` 由 `raw[required_columns].copy()` 得出，`:2991` 改读 `raw.get("tot_v")`。索引对齐安全：`dropna` 发生在 `:2993`，晚于 `tot_v` 赋值
  （等价替代方案：把 `tot_v` 并入 `required_columns` 一并保留。二者行为等价，实施时取其一）
- **建议映射的方法**：M-L2-03 Replace Temp with Query
- **风险**：中（涉及 DataFrame 列裁剪与索引对齐顺序，写错会让 `tot_v` 错位；`stock_zh_a_hist` 有 8 个用例覆盖）
- **验证**：AI 自证（全量 114 例，重点 `AutoAProcessingCharacterizationTest`；断言改动前后 `tot_v` 列的取值与行序一致）
- **范围**：约 12 行 / 1 文件

### [12] AUTOA `calculate_atr` 用已取的 numpy 数组末元素替代 `iloc` 重取

- **位置**：`tokenDemo/autoTrade_pm.py:2514-2515`
- **分类**：性能
- **现状**：`:2499-2501` 已取 `highs = hist_data["high"].values` / `lows` / `closes`，`:2514-2515` 又 `float(hist_data.iloc[-1]["high"])` / `["low"]`
- **问题**：同一份数据取两次，第二次走 pandas 的 `iloc` + 列标签查找（比 `highs[-1]` 慢一个量级），且两条取值路径同源却写法不同，读者需确认是否有意为之
- **建议**：改为 `latest_high = float(highs[-1])` / `latest_low = float(lows[-1])`
- **建议映射的方法**：M-L2-03 Replace Temp with Query
- **风险**：低（纯局部 2 行；`calculate_atr` 有 14 处测试引用）
- **验证**：AI 自证（全量 114 例；断言返回 ATR 数值与改动前逐位相同）
- **范围**：约 3 行 / 1 文件

### [13] 删 `calculate_atr` 中恒假的 `len(tr_list) < period` 守卫

- **位置**：`tokenDemo/autoTrade_pm.py:1382-1396` 区间内的长度守卫
- **分类**：可读性
- **现状**：函数开头已按 K 线根数做过长度前置守卫，随后又判一次 `if len(tr_list) < period:`
- **问题**：`tr_list` 长度由入参 K 线根数唯一决定，前置守卫已保证其 ≥ period，该条件恒假、分支不可达
- **建议**：删该 `if` 与其分支体，在前置守卫处补一行注释说明它已覆盖 `tr_list` 长度
- **建议映射的方法**：M-L2-09 Remove Redundant Conditional
- **风险**：低（`calculate_atr` 有 14 处测试引用，含短 K 线边界用例）
- **验证**：AI 自证（全量 114 例；另手工代入 period 与最短合法 K 线长度复核前置守卫确实蕴含该条件）
- **范围**：约 5 行 / 1 文件

### [14] 删 `from_cfg` 的 `slot_balance` 注入

- **位置**：`tokenDemo/autoTrade_pm.py:475`
- **分类**：可读性
- **现状**：`obj.slot_balance = kwargs.get("slot_balance", [0.0])`
- **问题**：`slot_balance` 全项目零读取方（资金分槽口径早已废弃），仅此一行赋值。留着会让人以为存在按槽位分配资金的机制
- **建议**：删该行，同步删 `:393-397` 注释里的 `slot_balance` 键名
- **建议映射的方法**：M-L2-10 Remove Dead Code
- **风险**：低（grep 零引用）
- **验证**：AI 自证（grep `slot_balance` 全项目零残留；全量 114 例）
- **范围**：约 2 行 / 1 文件

### [15] 合并 AUTOA 切比雪夫里两条完全相同的 DataFrame 分支

- **位置**：`tokenDemo/autoTrade_pm.py:2560-2566`
- **分类**：可读性
- **现状**：
  ```python
  if data.shape[1] != 1:
      series = data.iloc[:, 0]
  else:
      series = data.iloc[:, 0]
  ```
- **问题**：两分支体逐字相同，条件判断无任何作用。读者会花时间找"多列时到底取哪列"的差异，实际不存在
- **建议**：收成单行 `series = data.iloc[:, 0]`（保持"始终取第一列"的现有行为），加一句注释说明多列输入只取首列
- **建议映射的方法**：M-L2-09 Remove Redundant Conditional
- **风险**：低（两分支同体，删条件不可能改行为）
- **验证**：AI 自证（全量 114 例）
- **范围**：约 7 行 / 1 文件

### [16] `_manage_position` 的 `hl2` 上提为单次计算

- **位置**：`tokenDemo/autoTrade_pm.py:1832`、`:1849`
- **分类**：性能
- **现状**：ATR 初始化分支内 `:1832` 算一次 `hl2 = (kline[-1][2] + kline[-1][3]) / 2`；`:1846` 的早退判断之后 `:1849` 又算一次同式
- **问题**：同一表达式在同一函数内算两次，且两处字面量下标（`[2]` / `[3]`）各写一遍，改 hl2 口径要同步改 2 处
- **建议**：把 `hl2` 上提到 `:1825`（`atr_value = self.calculate_atr(kline)` 旁）一次算出，`:1832` 与 `:1849` 都改为复用
- **建议映射的方法**：M-L2-03 Replace Temp with Query
- **风险**：中（audit 原判置信度 **medium**）。等价性论证：`_close_triggered_position` 不接收 `kline`、无法改写它，故上提后取值不变；**唯一差异**是 `:1846` 早退路径上会多算一次纯算术（两次取下标 + 一次加法除法，无副作用、无 IO）。这是全轮唯一"某条路径多执行一点计算"的条目
- **验证**：AI 自证（全量 114 例；`_manage_position` 仅 2 处测试引用——`:1290` 直接 await、`:2451` AsyncMock——覆盖偏薄，需额外断言早退路径的返回值不变）
- **范围**：约 8 行 / 1 文件

### [17] `get_symbols_info` 的 `exchange_info` 改必填，删不可达兜底

- **位置**：`tokenDemo/autoTrade_pm.py:2195-2198`
- **分类**：结构
- **现状**：`def get_symbols_info(self, exchange_info=None)`，内部 `if exchange_info is None: exchange_info = self.market_client.rest_api.exchange_information()`
- **问题**：兜底分支不可达——唯一调用点 `:2344` 始终传参（AST 已证：1 处调用、1 个位置参）。且该分支**一旦走到必炸**：SDK 的 `exchange_information` 返回 `ApiResponse` 包装对象而非裸 dict（同文件 `:531-534` 的同类兜底正确地过了 `_unwrap_api_response`），紧接着 `:2205` / `:2215` 的 `exchange_info["symbols"]` 会抛 `TypeError`。它还绕过了 `_call_api` 的限流与超时
- **建议**：签名改 `def get_symbols_info(self, exchange_info):`，删 `if exchange_info is None:` 两行。唯一调用点 `:2344` 已按位置传参，无需改动。**不选"补 `_unwrap_api_response`"**——那是修一条写错的代码路径（修 bug，走 `cs-issue`），本轮只做行为等价删除
- **建议映射的方法**：M-L2-10 Remove Dead Code + M-L1-01 Parallel Change（签名变更走调用点枚举）
- **风险**：低（AST 枚举确认调用点唯一且传参形态兼容；测试侧 `:1880` 亦为 `obj.get_symbols_info(exchange_info)` 位置传参）
- **验证**：AI 自证（附调用点形态清单；grep `get_symbols_info(` 全项目仅定义 + 2 处调用，均传参；全量 114 例）
- **范围**：约 4 行 / 1 文件
