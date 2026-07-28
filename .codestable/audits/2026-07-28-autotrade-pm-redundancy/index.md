---
doc_type: audit-index
audit: 2026-07-28-autotrade-pm-redundancy
scope: tokenDemo/autoTrade_pm.py 全量扫描冗余判断 / 无用代码 / 重复调用 / 重复代码未封装四类问题
created: 2026-07-28
status: active
total_findings: 17
---

# autoTrade_pm.py 冗余与重复专项审计

## 范围

用户原话：「整个脚本再细细检查下，是否还有冗余的判断，无用的代码，重复的调用，重复的代码没封装。」

- **文件**：`tokenDemo/autoTrade_pm.py` 单文件，3682 行 / 160KB，含 `AUTOBN`（`:294-2411`）、`AUTOA`（`:2412-3554`）两个策略类与模块级工具（`:1-293`）。
- **维度**：只扫用户点名的四类，不是 cs-audit 默认的五维。安全维度未扫，性能维度只在"重复调用"这条线上顺带覆盖。
- **不在范围**：`autoTrade.py` / `autoTrade_papi.py` 两个遗留副本（三个文件有大量同源代码，但用户指定的是 PM 版）。跨文件的三副本重复问题不在本轮，见文末。

方法：先跑一遍收窄过的 ruff 机械基线（`--select F401,F811,F841,ARG,ERA,SIM,RET,C4,B,PLR,PIE`，55 项）作为已知项喂进扫描，避免把 lint 能查的东西当审计成果重述；再按代码区域 + 问题类型双向切分并行扫描，每条发现过两个对抗视角（"抹掉它有没有执行路径会变" + "引用的代码在那一行真的存在吗"），两个视角都不能推翻才留下。**45 条候选被对抗验证否掉**，最终留 17 条。

## 总评

这个文件在四个维度上的主病不是零散笔误，是**两类系统性成因**叠在一起：

1. **迁移遗留**。风险定仓、统一账户（PM）、企业微信 + PushPlus 通知这几轮演进之后，旧口径的配置项和分支仍挂在原地不删：`margin_mode`（#03）、`slot_balance`（#14）、个人微信发送分支（#07）、五枚失联常量（#08）。它们的共同特征是**看起来可配、实际不生效**——最坑的是 `BD_OI_PEAK_LOOKBACK` / `BD_VOLUME_PEAK_MIN_AGE` 这两枚，注释写得很清楚，值也对，但 `_is_bd_observation` 里全是硬编码字面量，改常量不会有任何反应。
2. **多空/多路径复制**。开仓信号的多头段（`:1985-2013`）与空头段（`:2027-2055`）近乎逐行复制（#06）；`close_bn_position` 的三条平仓路径各自抄了一份清理动作（#01）。复制出来的分支又各自长出恒真/恒假的守卫（#02、#05、#13）和同参重算（#04、#16）。

**最值得先动的是开平仓主路径那一组**（#01 / #02 / #04+#05），因为它们落在真实交易控制流上，且 `test_autoTrade_pm.py` 已有对应用例可兜回归。其中 #04+#05 是同一段代码的两个侧面（重复调用 + 死分支），必须一次改完——今天推送给用户的止盈止损值和实际挂单值恒等，但它们来自两条独立计算路径，任何单侧改动都会造成"通知数字对、单子不对"的静默分叉。

配置残骸（#03 / #07 / #08 / #14）建议紧随其后成批删，理由不是省几行代码，是防止运维照着注释以为某个模式/槽位/BD 窗口已经生效。

切比雪夫返回壳、DataFrame 双分支、`hl2` 二次计算一类属可读性或微冗余，可并入同一轮扫尾，不必单独立项。

## 发现清单

| # | 用户维度 | 性质 | 严重度 | 置信度 | 标题 | 位置 |
|---|---|---|---|---|---|---|
| [01](finding-01.md) | 重复代码未封装 | maintainability | P1 | high | `close_bn_position` 三处平仓清理块重复未封装 | `:893,965,999` |
| [02](finding-02.md) | 冗余判断 | maintainability | P1 | high | DCA 开仓失败后的 strategy 回滚条件恒真 | `:1616,1735` |
| [03](finding-03.md) | 无用代码 | maintainability | P1 | high | `from_cfg` 解析并写入 `margin_mode`，全文件无读取 | `:407-426` |
| [04](finding-04.md) | 重复调用 | performance | P2 | high | 开仓路径 `calc_stop_profit_loss` 同参计算两次 | `:1989,2031,2065` |
| [05](finding-05.md) | 冗余判断 | maintainability | P2 | high | `should_open` 后 atr/hl2 兜底与二次止盈止损是死路径 | `:2061-2069` |
| [06](finding-06.md) | 重复代码未封装 | maintainability | P2 | high | 多空开仓观察信号块结构近乎复制未抽取 | `:1985-2013,2027-2055` |
| [07](finding-07.md) | 无用代码 | maintainability | P2 | high | 个人微信 `wx=True` 分支及 `wx_key`/`user_name` 不可达 | `:429-434,628-642` |
| [08](finding-08.md) | 无用代码 | maintainability | P2 | high | 五枚类常量零引用，三枚与 BD 入池硬编码切片数值重合 | `:308,314,327,343-344` |
| [09](finding-09.md) | 无用代码 | performance | P2 | high | 切比雪夫返回值里 `message` 等字段从未被消费 | `:1456-1523` |
| [10](finding-10.md) | 冗余判断 | maintainability | P2 | high | SHORT 分支对 `completed_oi is None` 的二次判空恒与 `realtime_oi` 同步 | `:1143-1144` |
| [11](finding-11.md) | 重复调用 | performance | P2 | high | `stock_zh_a_hist` 对同一 `res` 重复构建 DataFrame | `:2980,2991` |
| [12](finding-12.md) | 重复调用 | performance | P2 | high | AUTOA `calculate_atr` 已取 numpy 数组又用 `iloc` 重取最新高低价 | `:2499-2515` |
| [13](finding-13.md) | 冗余判断 | maintainability | P2 | high | `calculate_atr` 中 `len(tr_list) < period` 在前置守卫后恒假 | `:1382-1396` |
| [14](finding-14.md) | 无用代码 | maintainability | P2 | high | `slot_balance` 只在 `from_cfg` 赋值，全项目无人读取 | `:473-475` |
| [15](finding-15.md) | 冗余判断 | maintainability | P2 | high | AUTOA 切比雪夫的 DataFrame 两分支完全相同 | `:2560-2566` |
| [16](finding-16.md) | 重复调用 | maintainability | P2 | **medium** | ATR 初始化路径上 `hl2` 计算两次 | `:1832,1849` |
| [17](finding-17.md) | 无用代码 | **bug** | P2 | high | `get_symbols_info` 的兜底分支不可达且缺 `_unwrap_api_response`，走到必炸 | `:2197-2198` |

## 按用户四维度分布

| 用户维度 | P1 | P2 | 合计 |
|---|---|---|---|
| 冗余判断 | 1 | 4 | 5 |
| 无用代码 | 1 | 5 | **6** |
| 重复调用 | 0 | 4 | 4 |
| 重复代码未封装 | 1 | 1 | 2 |
| **合计** | **3** | **14** | **17** |

> **无用代码这一维超了 cs-audit 的「每维 ≤5 条」上限**，超的是 #17。刻意破例，理由：#17 是全轮唯一性质为 `bug` 的发现（其余 16 条全是 `maintainability` / `performance`），且它不是工作流产出而是交叉核查时补的覆盖缺口。为凑格式把唯一一条真缺陷压到未排入区，代价与收益不成比例。其余三维均在上限内。

## 按性质 × 严重度分布

| 性质 | P0 | P1 | P2 | 合计 |
|---|---|---|---|---|
| bug | 0 | 0 | 1 | 1 |
| security | 0 | 0 | 0 | 0 |
| performance | 0 | 0 | 4 | 4 |
| maintainability | 0 | 3 | 9 | 12 |
| arch-drift | 0 | 0 | 0 | 0 |
| **合计** | **0** | **3** | **14** | **17** |

零 P0：本轮四个维度天然不产 P0——冗余和重复不会让现网当场出错。唯一的 `bug` 性质条目（#17）也因分支不可达而无现网影响。

## 与既有审计的交叉引用

同文件此前有两份审计。本轮**不标它们 superseded**——维度不重叠，旧审计仍有本轮不覆盖的条目。

`2026-07-11-auto-trade-efficiency`（效率专项）与本轮在"重复调用"上有交集，逐条核查其状态：

| 旧条目 | 现状 | 依据 |
|---|---|---|
| F02 平仓 Excel 全量重写 | **已修** | `:165` `_pending_records` 批量缓冲 + `:274` `flush_pending_records`，`:3668` 退出兜底 flush |
| F03 每 15 分钟重复取全量元数据 | **已修** | `:312` `EXCHANGE_INFO_CACHE_TTL = 6h` + `:2180-2193` TTL 缓存 |
| F04 多空比缓存未覆盖 5m | **已修** | commit `5d6bdd24` 的末根时间戳单调推进协议；旧条目引用的 `get_long_short_ratio` 在本文件已不存在 |
| F07 交易路径重复仓位查询 | **已修** | `:2219` `get_position_risk(position_risk=None)` 退化为纯变换，由 `:2342` 传入已取数据 |
| F01 / F08 AUTOA 行情重复 + 缺 single-flight | **未核实** | `_get_sina_intraday_price` 现仅 `:2745` 一处调用，旧条目引的第二处消费者未在本轮维度内确认 |
| F05 AUTOA 收盘涨停池串行请求 | **不在本轮维度** | 纯并发/性能，与冗余重复无关 |

结论：旧审计的"重复调用"类基本关闭，所以本轮 #04 / #11 / #12 / #16 是新发现而非回锅。建议在旧 audit 目录里把 F02 / F03 / F04 / F07 标 `status: resolved`——那是文档卫生，不属本轮改动。

另一份 `2026-06-28-auto-trade-performance`（`status: active`）针对平仓/监控性能，与本轮四维度无交集，无需处理。

## 本轮未排入的条目及原因

对抗验证活下来但没进清单的 9 条，按 cs-audit「不许静默截断」记全：

| 维度 | 条目 | 位置 | 未排入原因 |
|---|---|---|---|
| 无用代码 | `CloseRecordManager.IO_TIMEOUT_SECONDS` 零引用 | `:159` | 单枚未用超时常量，不误导控制流，弱于 #08 那组"假可配" |
| 无用代码 | `_normalize_account_info` 写入的 `raw` 字段无人读取 | `:540-545` | 只多挂一个引用，无"假生效"误导，收益仅省内存 |
| 无用代码 | `check_side` 的 `kline_close` 形参完全未使用 | `:1131` | 死形参，ruff ARG 已标，本轮优先交易路径与配置残骸 |
| 无用代码 | `_manage_position` 的 `current_timestamp` 形参完全未使用 | `:1822` | 同上，死形参 |
| 无用代码 | `symbols_info` 的 `quotePrecision` 键写入后无读取 | `:2211` | 单键未读，影响面小于整段死枝 |
| 无用代码 | AUTOA 切比雪夫的 `message` 字段无读取方 | `:2583-2648` | 与 #09 同模式同主题，#09 已覆盖 |
| 无用代码 | 平仓 `close_reason` 末支 `elif` 不可达 | `:3172-3179` | 不可达成立，但只影响赋值文案 |
| 冗余判断 | `MIN_CHEB_SAMPLE_SIZE` 长度闸在缓存协议下不可达 | `:1174-1181` | 置信度 medium（可视为协议漂移防护），弱于其它 high 的恒真/恒假 |
| 冗余判断 | 切比雪夫 `not data_list or len(...) == 0` 重复 | `:1453-1454` | 对 list 两者语义等价，纯可读性，改动收益最低 |

另有 4 条候选与已排入条目实为同一问题的不同叙述（`slot_balance`→#14、五枚死常量→#08、DataFrame 双分支→#15、两个死形参的合并叙述→上表第 3/4 行），已合并不重复计数。

**已知但刻意不报**的：ruff 机械项（55 项，跑一次 lint 即得，不重述）、全角标点 RUF001/002/003 噪音、以及 `autoTrade.py` / `autoTrade_papi.py` 与本文件的三副本重复——后者是真问题但跨文件、影响面远超本轮范围，若要处理应单独开 `cs-refactor` 立项。

## 本轮方法学的诚实交代

- 工作流 183 个 agent 中 **12 个因网关 524 失败**：4 个 finding 写手（`finding-04` / `07` / `08` 未落盘，`14` 重试后成功）、6 个对抗验证 agent、1 个补充 finder、1 个 critic。
- 因此**清单里 17 条的行号与核心论断我全部手工复核过一遍**（逐条打开源码对照），不依赖失败 agent 的结论。`finding-04` / `07` / `08` / `17` 四份由我手写，各自在"对抗验证记录"节标明了验证来源。
- 一处自我更正记录在 #17 里：我最初判断 `:2198` 是"缺 await 会拿到协程对象"，读 `_call_api:692` 的 `asyncio.to_thread(method, ...)` 后确认 SDK 方法是同步的，真实缺陷是缺 `_unwrap_api_response` 拆包。结论不变，机制不同。
- 覆盖缺口：#17 是我在做旧审计交叉核查时撞见的，10 个区域 finder 与 5 个 lens finder 都没报出来。说明区域切分对"函数默认参数的兜底分支"这类模式敏感度不足。

## 下一步建议

cs-audit 只发现不定修。下面按优先级给路由，选哪条由你定。

**第一批 · 开平仓主路径（建议 `cs-refactor`，一次做完）**

1. #01 抽 `_clear_closed_position(symbol, close_info, ts)`，三个调用点收成单行
2. #02 DCA 失败分支改无条件 `strategy.pop()`（或换 assert / 注释）
3. #04 + #05 **必须一起改**：`should_open` 段复用 `zy_msg` / `zs_msg`，删 `:2061-2064` 死兜底、`:2065-2067` 二次计算、`:2068-2069` 死早退

三条都在真实交易控制流上，回归点清晰，现有测试可兜。

**第二批 · 配置与死枝清理（建议 `cs-refactor`，成批删）**

4. #03 删 `margin_mode` 解析与赋值
5. #14 删 `slot_balance`
6. #07 删 `send_msg` 的 `wx` 形参与整个 `if wx:` 分支、`wx_key` / `user_name` 及 `:396` 注释残留（24 个调用点均不需改）
7. #08 五枚常量：BD 三枚建议接线到 `_is_bd_observation` 的硬编码切片，`MIN_KLINE_FOR_ANALYSIS`（值与真实门槛 30 矛盾）与 `LONG_SHORT_RATIO_SHORT_LIMIT` 直接删
8. #17 `get_symbols_info` 的 `exchange_info` 改必填参数

这批的价值是让配置面诚实——不修的话运维会继续按注释以为某些开关生效。

**第三批 · 信号与工具函数扫尾（建议 `cs-refactor`）**

9. #10 去 `completed_oi` 双判空
10. #13 删 `calculate_atr` 恒假守卫；#09 精简切比雪夫返回壳；#15 合并 AUTOA DataFrame 双分支
11. #11 复用已构建的 DataFrame；#12 用 `highs[-1]` / `lows[-1]` 替代 `iloc` 重取
12. #16 `hl2` 单次计算（置信度 medium，改前先确认 `:1843` 早退路径）
13. #06 抽多空开仓观察块——放最后，因为它是本轮改动面最大的一条，等前面把死分支清干净再抽，抽出来的公共函数才不会把冗余一起带进去

**未排入的 9 条**：可作第二轮清理，不阻塞上面任何一批。

**跨文件三副本重复**：如要处理，单独开 `cs-refactor` 立项，本轮不建议顺手动。
