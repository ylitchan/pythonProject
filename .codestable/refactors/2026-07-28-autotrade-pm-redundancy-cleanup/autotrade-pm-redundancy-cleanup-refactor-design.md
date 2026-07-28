---
doc_type: refactor-design
refactor: 2026-07-28-autotrade-pm-redundancy-cleanup
status: approved
scope: tokenDemo/autoTrade_pm.py 单文件，清理 cs-audit 的 17 条发现并纳入用户确认的 3 条 AUTOA/BD 同形补充项
summary: 20 条候选并入 7 个执行步骤，分 3 批推进（死代码与常量 → 局部等价改写 → 主路径封装），全程保持现有交易行为
---

# autotrade-pm-redundancy-cleanup refactor design

## 1. 本次范围

- **改动文件**：`tokenDemo/autoTrade_pm.py`（唯一）
- **新增测试**：`tokenDemo/test_autoTrade_pm.py`（仅新增 #09 的刻画测试，不改既有用例）
- **纳入原审计 17 条 + 讨论中确认的 3 条补充项**：AUTOA `send_msg` 位置参数防错绑、AUTOA 切比雪夫 `message`、AUTOA 平仓原因不可达末支；执行归并为 checklist 的 7 步
- **用户确认的 #08 口径**：删除五枚失联旧常量，复用 `KLINE_LIMIT` / `OI_QUERY_LIMIT`，新增并接线成交量与 OI 各自独立的 10/3 窗口常量；删除入口已保证的 K 线长度重复判断
  2. **不给 `get_symbols_info` 补 `_unwrap_api_response`**（#17 只删不修）——那是修一条写错的代码路径，走 `cs-issue`
  3. **不动 `_is_bd_observation` 的 `:1884` / `:1894-1901`** 任何一行
  4. **不动切比雪夫除 `message` 外的其余返回字段**（`mean` / `std` / `k` / `deviation` / `min_probability_in_range` 虽也无人消费，但它们是文档化的返回契约，收窄属接口变更）
  5. **不碰 `autoTrade.py` / `autoTrade_papi.py` / `autoBN_v2.py` 的同源副本**（跨文件三副本重复需单独立项）
  6. **不修 audit 未排入的 9 条**（可作第二轮，不阻塞本轮任何一步）
- **预估工作量**：约 250 行触碰面（净减约 130 行），16 次提交
- **总风险档位**：**中**。逐步风险：低 9 步 / 中 6 步 / 高 1 步（步骤 16）

## 2. 前置依赖

| 前置 | 服务于 | 动作 | 为什么必须先做 |
|---|---|---|---|
| **P1 补切比雪夫刻画测试** | 步骤 6（#09） | 新增用例固化 `calculate_chebyshev_probability` 在 4 种输入下的 `chebyshev_upper_bound`：k≤1、k>1、`std == 0`、单元素 `data_list`。**只断言被消费的键，不断言 `message`** | 现有 114 个用例里该函数被 `MagicMock` 整体替换（`test_autoTrade_pm.py:1942`），函数体零覆盖。没有这组测试，"行为等价"只是口头承诺 |
| **P2 调用点实参形态枚举** | 步骤 4（#17）、步骤 5（#07） | 用 AST 脚本按"接收者 + 位置参个数 + 关键字名"分组枚举，把清单贴进 apply-notes | **本项目有真实事故先例**：`2026-07-25-auto-trade-dead-code` 删 `stock_zh_a_hist.fields` 时断言"所有调用方均未传入"，但 4 个调用点是**位置传参**，删后字符串静默绑到 `start_date`，AUTOA 全部日线路径失败。文本 grep 看不出实参形态，必须枚举 |
| **P3 基线留档** | 全部 | 记录改动前基线：`uv run python -m unittest tokenDemo.test_autoTrade_pm -q` → 114 例 / OK（已跑通，1.842s） | 每步的退出信号都以此为参照 |

P2 已在 scan 阶段跑过一轮，结论：
- `self.send_msg`（AUTOBN）**24 处**：22 处仅 1 个位置参，2 处为 `(msg, qy_key=...)`。**无一处有第 2 个位置参** → 删 `wx` 形参 + 加 `*` 均安全
- `self.get_symbols_info` **1 处**（`:2344`）：1 个位置参 → 改必填安全；测试侧 `:1880` 亦为位置传参
- 顺带发现（**本轮不动，记录备查**）：`cls.send_msg`（AUTOA）8 处中有 2 处按位置传第 2 个参数（`:3211`、`:3351` 位置传 `pushplus_notification`）。AUTOA 的 `send_msg` 是独立实现，本轮不碰，但它是同一种事故形态，将来若改其签名必须先枚举

## 3. 执行顺序

**批次划分的理由**（与 audit 建议的顺序有一处调整）：audit 建议"主路径优先、配置残骸随后"。本方案把**纯删除提到最前**，因为 ①步骤 16（#06 抽公共函数）必须等 #04+#05 把死分支清掉，而死分支清理天然属于删除批 ②先积累一批零行为面的干净 diff，能把"测试仍全绿"确立为可信基线，再动交易主路径。

每步一次提交，提交粒度 = 回滚粒度。批间设硬 checkpoint。

---

### 批次一 · 纯删除（步骤 1-6，零行为面）

#### 步骤 1：删 `from_cfg` 的 `margin_mode` 解析与赋值（#03）
- 引用方法：M-L2-10 Remove Dead Code
- 具体操作：删 `:409-426`（`margin_mode_raw` 规范化、`margin_mode_map` 8 项映射表、`obj.margin_mode` 赋值）；删 `:393-397` 注释里的 `margin_mode/position_mode` 键名
- 退出信号：`grep -rn "margin_mode\|position_mode"` 全项目零命中；114 例全绿
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交

#### 步骤 2：删 `from_cfg` 的 `slot_balance` 注入（#14）
- 引用方法：M-L2-10 Remove Dead Code
- 具体操作：删 `:475` 一行；删 `:393-397` 注释里的 `slot_balance` 键名
- 退出信号：`grep -rn "slot_balance"` 全项目零命中；114 例全绿
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交

#### 步骤 3：删五枚零引用类常量（#08）
- 引用方法：M-L2-10 Remove Dead Code
- 具体操作：删 `:308` `MIN_KLINE_FOR_ANALYSIS`、`:314` `LONG_SHORT_RATIO_SHORT_LIMIT`、`:327` `OI_LOOKBACK_PERIOD`、`:343` `BD_OI_PEAK_LOOKBACK`、`:344` `BD_VOLUME_PEAK_MIN_AGE`。**`_is_bd_observation` 一行不动**
- 退出信号：逐枚 grep 全项目零命中；114 例全绿
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交

#### 步骤 4：`get_symbols_info` 的 `exchange_info` 改必填（#17）
- 引用方法：M-L2-10 Remove Dead Code + M-L1-01 Parallel Change
- 具体操作：签名 `def get_symbols_info(self, exchange_info):`；删 `:2197-2198` 的 `if exchange_info is None:` 两行。调用点 `:2344` 不改
- 退出信号：P2 清单贴进 apply-notes；`grep -n "get_symbols_info("` 仅定义 + 2 处调用且均传参；114 例全绿
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交

#### 步骤 5：删 `send_msg` 的 `wx` 形参与 `if wx:` 分支，`qy_key` 收为仅关键字（#07）
- 引用方法：M-L2-10 Remove Dead Code + M-L1-01 Parallel Change
- 具体操作：签名改 `async def send_msg(self, msg: str, *, qy_key: Optional[str] = None) -> None`；删 `if wx:` 整段（`:628-642`），`else` 体上提；删 docstring 里 `wx` 说明；删 `obj.wx_key` / `obj.user_name`（`:429-434`）与 `:393-397` 注释残留。24 个调用点不改
- 退出信号：P2 清单贴进 apply-notes；`grep -rn "wx_key\|user_name\|WX_KEY\|USER_NAME\|wechatpadpro"` 全项目零命中；114 例全绿（`send_msg` 在测试侧有 24 处引用，需确认无一处依赖 `wx` 形参）
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交

#### 步骤 6：删切比雪夫返回值的 `message` 构造（#09）
- 引用方法：M-L2-10 Remove Dead Code（**前置 P1 必须先完成**）
- 具体操作：删 `:1464`、`:1486` 两处 `result["message"] = ...`；删 `:1511-1523` 正常出口那组仅服务文案的 `if k <= 1 / else`。**保留 `:1494-1500` 那组**——它算的是被消费的 `chebyshev_upper_bound`
- 退出信号：P1 新增用例全绿；`grep -n '\["message"\]\|\.get("message")'` 在 AUTOBN 侧零消费；114 + 新增例全绿
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交（P1 的测试保留）

> **批次一 checkpoint**：向用户汇报 6 步 diff 与测试结果，等确认后进批次二。

---

### 批次二 · 恒真恒假与重复计算（步骤 7-13，局部等价改写）

#### 步骤 7：DCA 回滚改无条件 `pop()`（#02）
- 引用方法：M-L2-09 Remove Redundant Conditional
- 具体操作：`:1617-1620`（多头）与 `:1736-1739`（空头）的守卫删掉，改为无条件 `close_info.strategy.pop()`，各加一行注释指向 `:1587` / `:1706` 的配对 append
- 退出信号：`grep -n "close_info.strategy"` 写入点仍为 4 处；114 例全绿（`_manage_long_position` / `_manage_short_position` 各 3 例）
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交

#### 步骤 8：删 SHORT 分支 `completed_oi` 二次判空（#10）
- 引用方法：M-L2-09 Remove Redundant Conditional
- 具体操作：`:1143-1144` 收成 `if realtime_oi is None:`，加注释"`_get_bd_oi_windows` 两值同生同灭"
- 退出信号：读 `_get_bd_oi_windows` 全部 return 语句复核"同生同灭"；114 例全绿
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交

#### 步骤 9：删 `calculate_atr` 恒假长度守卫（#13）
- 引用方法：M-L2-09 Remove Redundant Conditional
- 具体操作：删 `:1382-1396` 区间内的 `if len(tr_list) < period:` 与其分支体；在前置守卫处补注释说明它已蕴含 `tr_list` 长度
- 退出信号：手工代入 period 与最短合法 K 线长度复核蕴含关系；114 例全绿（含短 K 线边界用例）
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交

#### 步骤 10：合并 AUTOA 切比雪夫 DataFrame 双分支（#15）
- 引用方法：M-L2-09 Remove Redundant Conditional
- 具体操作：`:2560-2566` 收成单行 `series = data.iloc[:, 0]`，加注释"多列输入只取首列"
- 退出信号：114 例全绿
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交

#### 步骤 11：AUTOA `calculate_atr` 用 `highs[-1]` / `lows[-1]` 替代 `iloc` 重取（#12）
- 引用方法：M-L2-03 Replace Temp with Query
- 具体操作：`:2514-2515` 改为 `latest_high = float(highs[-1])` / `latest_low = float(lows[-1])`
- 退出信号：断言返回 ATR 与改动前逐位相同；114 例全绿
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交

#### 步骤 12：`stock_zh_a_hist` 保留原始 DataFrame 供 `tot_v` 取用（#11）
- 引用方法：M-L2-03 Replace Temp with Query
- 具体操作：`:2980` 改为 `raw = pd.DataFrame(res)`；`:2987` 改为 `hist_today = raw[required_columns].copy()`；`:2991` 改读 `raw.get("tot_v")`。**注意**：`:2987` 的列裁剪丢掉了 `tot_v`，`:2991` 原本是为把它取回来才重建 DataFrame——这不是笔误，改法必须保住取值。索引对齐安全：`dropna`（`:2993`）晚于 `tot_v` 赋值
- 退出信号：断言 `tot_v` 列取值与行序与改动前一致；114 例全绿（重点 `AutoAProcessingCharacterizationTest`）
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交

#### 步骤 13：`_manage_position` 的 `hl2` 上提为单次计算（#16）
- 引用方法：M-L2-03 Replace Temp with Query
- 具体操作：`hl2` 上提到 `:1825`（`atr_value = self.calculate_atr(kline)` 旁）一次算出，`:1832` 与 `:1849` 改为复用
- 退出信号：额外断言 `:1846` 早退路径的返回值不变；114 例全绿
- 验证责任：AI 自证
- 回滚：`git revert` 本步提交

> **批次二 checkpoint**：向用户汇报 7 步 diff 与测试结果，等确认后进批次三。

---

### 批次三 · 开平仓主路径封装（步骤 14-16，改动面最大）

#### 步骤 14：`should_open` 段复用 `zy_msg`/`zs_msg`，删死兜底与死早退（#04 + #05）
- 引用方法：M-L2-03 Replace Temp with Query + M-L2-10 Remove Dead Code + M-L2-09 Remove Redundant Conditional
- 具体操作：删 `:2061-2064`（`None` 兜底，含一次多余 `calculate_atr`）、`:2065-2067`（同参二次 `calc_stop_profit_loss`）、`:2068-2069`（`zy == 0 and zs == 0` 死早退）；`open_bn_position` 直接吃 `zy_msg` / `zs_msg`。**必须一次改完，不许拆**
- 退出信号：断言 `open_bn_position` 收到的 `zy`/`zs` 与推送消息里的数值同源；`grep` 确认 `rzq_token` 内 `hl2`/`atr_value` 写入点只剩两个信号段；114 例全绿（`rzq_token` 15 例 + `AutoBNLongSignalTest` / `AutoBNShortSignalTest`）
- 验证责任：AI 自证 + **HUMAN**（本批完成后看一轮真实开仓推送，确认消息里的止盈止损与交易所挂单一致）
- 回滚：`git revert` 本步提交

#### 步骤 15：抽 `_clear_closed_position` 收拢三处平仓清理块（#01）
- 引用方法：M-L2-01 Extract Function
- 具体操作：新增 `_clear_closed_position(self, symbol, close_info)`，函数体内保留 `self._handle_closed_position_observation(symbol, close_info, time.time())` 与 `if symbol in self.alert_all["POSITIONS"]: pop(symbol)` **原样**（不换 `pop(symbol, None)`，那是另一条）；`:893-897`、`:965-969`、`:999-1003` 各收成单行调用
- 退出信号：`time.time` 的 patch 目标是模块级 `tokenDemo.autoTrade_pm.time.time`，移进 helper 后 patch 仍生效；**每条路径的 `time.time()` 调用次数保持 1 次不变**（测试里有 `side_effect=[100, 101]` 这类对调用次数敏感的桩）；114 例全绿（三条路径各有覆盖：A 路径 4 例、B 路径 2 例、C 路径 2 例）
- 验证责任：AI 自证 + **HUMAN**（看一轮真实平仓推送与 `close_records.xlsx` 落盘）
- 回滚：`git revert` 本步提交

#### 步骤 16：抽 `_build_open_signal` 消除多空两段复制（#06）
- 引用方法：M-L2-01 Extract Function（配合 M-L2-08 Guard Clauses）
- 具体操作：新增 `_build_open_signal(self, symbol, kline, is_long, lsr, basis_rate)`，返回 `(hl2, atr_value, zy_msg, zs_msg)` 或 `None`；把段内 `if not (zy_msg == 0 and zs_msg == 0):` 反转为守卫子句提前 return；两份重复的 `send_msg` f-string 收成一次调用 + 一个 `qy_key` 变量。`:1985-2013` / `:2027-2055` 两段收成各自一次调用 + 分支特有的 4 处差异（`is_long`、`basis_rate` 比较方向、`lsr` 取值、`OrderSide`）
- 前置条件：**步骤 14 已完成**（否则会把死分支抽进公共函数）
- 退出信号：逐字符 diff 两段推送文案确认渲染结果不变；114 例全绿
- 验证责任：AI 自证 + **HUMAN**（各看一次真实多头、空头开仓推送）
- 回滚：`git revert` 本步提交

> **收尾**：全量测试 + `uv run ruff check tokenDemo/autoTrade_pm.py`（只看本轮目标是否清零，不追既有 55 项机械基线）+ 用户整体确认。

---

## 4. 改了啥

### 4.1 一览（before → after）

| 步 | # | 位置 | before | after |
|---|---|---|---|---|
| 1 | 03 | `:409-426` `:393-397` | 读 `margin_mode`/`position_mode`，经 8 项映射表写 `obj.margin_mode` | 整段删除，注释同步删键名 |
| 2 | 14 | `:475` `:393-397` | `obj.slot_balance = kwargs.get("slot_balance", [0.0])` | 删除，注释同步删键名 |
| 3 | 08 | `:308,314,327,343,344` | 五枚常量定义 | 删除；`_is_bd_observation` 字面量保持原样 |
| 4 | 17 | `:2195-2198` | `exchange_info=None` + 不可达兜底 | `exchange_info` 必填，兜底删除 |
| 5 | 07 | `:429-434,601-603,628-642` | `send_msg(msg, wx=False, qy_key=None)` + `if wx:` 内网分支 + 2 个死字段 | `send_msg(msg, *, qy_key=None)`，只剩企业微信分支；2 字段与注释残留删除 |
| 6 | 09 | `:1464,1486,1511-1523` | 三个出口各构造中文 `message` f-string | `message` 不再构造；`chebyshev_upper_bound` 的计算分支保留 |
| 7 | 02 | `:1617-1620,1736-1739` | `if strategy and strategy[-1] == DCA: pop()` | 无条件 `pop()` + 配对注释 |
| 8 | 10 | `:1143-1144` | `if realtime_oi is None or completed_oi is None:` | `if realtime_oi is None:` + 契约注释 |
| 9 | 13 | `:1382-1396` | 前置守卫后再判 `len(tr_list) < period` | 删除该判断，前置守卫补注释 |
| 10 | 15 | `:2560-2566` | `if shape[1] != 1: … else: …` 两分支体相同 | 单行 `series = data.iloc[:, 0]` |
| 11 | 12 | `:2514-2515` | `float(hist_data.iloc[-1]["high"])` | `float(highs[-1])`（复用已取数组） |
| 12 | 11 | `:2980,2987,2991` | `pd.DataFrame(res)` 构建两次，第二次为取回被裁掉的 `tot_v` | 保留 `raw`，`tot_v` 从 `raw` 取，只构建一次 |
| 13 | 16 | `:1832,1849` | `hl2` 同式算两次 | 上提到 `:1825` 算一次，两处复用 |
| 14 | 04+05 | `:2061-2069` | 死 `None` 兜底 + 同参二次 `calc_stop_profit_loss` + 死早退 | 三段删除，下单直接吃 `zy_msg`/`zs_msg` |
| 15 | 01 | `:893,965,999` | 3 行清理块逐字重复 3 次 | 抽 `_clear_closed_position`，三处各一行 |
| 16 | 06 | `:1985-2013,2027-2055` | 两段 29 行近逐行复制，段内 f-string 各再重复 1 次 | 抽 `_build_open_signal`，两段各收成一次调用 |

### 4.2 结构层面的净变化

- **删**：1 个形参（`send_msg.wx`）、1 个可选形参转必填（`get_symbols_info.exchange_info`）、2 个实例字段（`wx_key`、`user_name`）、1 个实例字段（`margin_mode`）、1 个实例字段（`slot_balance`）、5 个类常量、1 个返回字段（`message`）、5 处不可达/恒真恒假分支
- **加**：2 个私有方法（`_clear_closed_position`、`_build_open_signal`）、1 个仅关键字屏障（`send_msg` 的 `*`）、1 组刻画测试（切比雪夫 4 例）
- **行数**：净减约 130 行（删约 145、加约 15）
- **签名变更 2 处**，均已用 AST 枚举全部调用点实参形态确认兼容

## 5. 有啥影响

### 5.1 对运行行为的影响：**零外部可观察变化**（逐类论证）

| 类别 | 步骤 | 为什么等价 |
|---|---|---|
| 删零引用符号 | 1,2,3 | grep 全项目零读取方，删除后无任何代码路径改变 |
| 删不可达分支 | 4,6(部分),14 | 静态可证明不可达：#17 唯一调用点始终传参；#05 由 `:1965-1967` 的 `None` 初始化 + `should_open=True` 仅在赋值之后置位证明 |
| 删恒真/恒假条件 | 7,8,9,10 | 条件依赖变量的**全部**写入点已枚举，各条可达路径取值固定 |
| 复用已算结果 | 11,12,13,14 | 被复用的是纯函数/纯表达式的结果，入参在两次求值之间无写入 |
| 抽函数 | 15,16 | 函数体逐字搬移，参数覆盖全部外部依赖，返回值覆盖全部对外产出 |
| 签名收窄 | 4,5 | AST 枚举确认所有实参形态兼容新签名 |

### 5.2 三处"严格意义上的差异"（必须知道，都不影响实际行为）

1. **步骤 6（#09）消掉一条潜在异常路径**：`message` 里有 `f"{value:.4f}"`，若 `value` 不可这样格式化，今天会抛异常，删后不抛。三个调用点传的都是 float（`oi_5m_last`、`max(oi_old)`、`current_volume`），实际不可达，但这是本轮唯一"删掉了一条异常路径"的改动。
2. **步骤 13（#16）在早退路径上多算一次纯算术**：`hl2` 上提后，`:1846` 早退时也会先算 `hl2`（两次取下标 + 一次加除）。无副作用、无 IO。audit 给这条的置信度是 medium，原因就在这里。
3. **步骤 5（#07）加 `*` 让 `qy_key` 只能关键字传**：这本身是**收紧**而非等价——今天写 `send_msg(msg, key)` 能跑（绑到 `wx`），改后会 `TypeError`。刻意为之：AST 已证 24 处全部用关键字形态，加 `*` 零成本，且永久杜绝 `fields` 那类位置传参错绑。

### 5.3 对配置与运维的影响（**需要通知运维**）

以下配置面在改动后**静默失效**（`from_cfg` 用 `**kwargs`，传了不会报错，会被忽略）：

| 配置 | 现状 | 改后 |
|---|---|---|
| `margin_mode` / `position_mode` 键 | 解析后写入 `obj.margin_mode`，但无人读 | 键被忽略 |
| `slot_balance` 键 | 赋值后无人读 | 键被忽略 |
| `wx_key` 键 / `WX_KEY` 环境变量 | 注入后只被不可达分支读 | 键与环境变量被忽略 |
| `user_name` 键 / `USER_NAME` 环境变量 | 同上 | 同上 |

**这些配置今天就已经不生效**——本轮改动只是让代码不再假装它们可配。**净收益正在这里**：运维不会再对着注释以为逐仓模式、资金分槽、个人微信通知是能开的开关。

顺带清掉两个不该留在仓库里的硬编码值：`:430` 形如真实 webhook key 的 UUID 默认值、`:433` 真实形态的群聊 ID。因分支不可达，今天不构成凭证泄露，但删除时一并清走。

### 5.4 对测试的影响

- **预期不需要修改任何既有用例**——全部 16 步都是行为等价，114 例应逐步保持全绿。任何一例变红都说明等价性论证有漏洞，该步退回。
- **新增**：#09 的 4 例刻画测试（前置 P1）。
- **两处覆盖偏薄，实施时额外补断言**：
  - `_manage_position` 只有 2 处测试引用（`:1290` 直接 await、`:2451` AsyncMock）→ 步骤 13 需额外断言早退路径返回值
  - `from_cfg` 零测试引用 → 步骤 1/2/5 的删除靠 grep 自证，不靠测试
- **一个易踩的坑**：测试里 `time.time` 是模块级 patch（`tokenDemo.autoTrade_pm.time.time`，19 处），且有 `side_effect=[100, 101]` 这类**对调用次数敏感**的桩。步骤 15 抽函数时必须保持每条路径 `time.time()` 调用次数为 1。

### 5.5 对可维护性的影响（做这轮的实际收益）

- **消除"通知数字对、单子不对"的静默分叉风险**（步骤 14）：今天推送的止盈止损与实际挂单值恒等，但来自两条独立计算路径，任一侧改动即分叉且无断言拦截。改后来源唯一。
- **开仓信号口径改一处而非两处 + 四份文案**（步骤 16）。
- **平仓清理口径改一处而非三处**（步骤 15）。
- **配置面诚实**（步骤 1/2/3/5）：不再有"改了没反应"的假开关。
- **签名诚实**（步骤 4/5）：`get_symbols_info()` 无参调用不再是编译期合法、运行期必炸；`send_msg` 的位置传参错绑通道被 `*` 永久关闭。

### 5.6 不做的代价

17 条全是 P1/P2，无 P0，**不做今天不会出错**。代价是延续两类系统性成因：迁移遗留的假配置继续误导调参，多空/多路径复制继续要求"改一处等于改 N 处"，而其中步骤 14 那处双路径计算是有真实分叉风险的——它不报错，只在某天让推送数字和实际挂单悄悄不一致。

## 6. 风险与看点

### 6.1 高风险步骤

| 步 | 风险 | 缓解 |
|---|---|---|
| **16**（#06） | 本轮改动面最大（约 60 行），落在开仓主路径，抽出的函数要返回 4 个值 | 排最后；前置要求步骤 14 完成；退出信号含"逐字符 diff 两段推送文案"；HUMAN 看真实多空开仓推送 |
| **14**（#04+05） | 改的是下单参数取值来源 | 不许拆步；断言 `open_bn_position` 入参与推送数值同源；HUMAN 看真实开仓推送 |
| **15**（#01） | 平仓主路径；`time.time()` 调用次数敏感 | 三条路径均有测试覆盖；退出信号显式检查调用次数；HUMAN 看平仓推送与 Excel 落盘 |
| **5**（#07） | 改公开签名，本项目有同类事故先例 | 强制 AST 枚举实参形态（P2），清单贴 apply-notes；加 `*` 关闭错绑通道 |
| **12**（#11） | DataFrame 列裁剪与索引对齐顺序，写错会让 `tot_v` 错位 | 明确记录"`:2991` 是为取回被 `:2987` 裁掉的列"这一机制；断言 `tot_v` 取值与行序不变 |
| **6**（#09） | 目标函数零真实覆盖 | 前置 P1 补刻画测试后才动手 |

### 6.2 容易出错的点

1. **把 #04 和 #05 拆成两步**——单侧改动会让"推送值"与"挂单值"从恒等变成两条独立路径，那正是这条要消除的风险本身。design 已把它们锁成步骤 14 一步。
2. **在步骤 16 之前做步骤 16**——若先抽公共函数，会把 `:2061-2069` 的死分支一起抽进去。前置条件已写死。
3. **#08 顺手"接线"**——看着是等价替换，实则把一枚常量绑到两个不同概念（量窗口 / OI 窗口）上，比现状更坏。已在"明确不做"里锁定只删。
4. **#17 顺手"补 `_unwrap_api_response`"**——那是修 bug，会让本轮从重构变成夹带行为改动。已锁定只删。
5. **#11 误以为"复用 `hist_today` 就行"**——`:2987` 的列裁剪丢掉了 `tot_v`，`:2991` 是为取回它才重建。直接删第二次构建会让 `tot_v` 变成 `NaN` 或 `KeyError`。
6. **#09 删错那组 `if k <= 1`**——`:1494-1500` 那组算的是被消费的 `chebyshev_upper_bound`，必须保留；只删 `:1512-1523` 那组文案分支。
7. **步骤 15 改成 `pop(symbol, None)`**——看着更简洁，但那是独立的一条改动，混进来会破坏"一步一件事"和单步回滚。
