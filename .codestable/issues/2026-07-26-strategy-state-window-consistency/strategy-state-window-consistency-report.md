---
doc_type: issue-report
issue: 2026-07-26-strategy-state-window-consistency
status: confirmed
severity: P1
summary: AUTOBN与AUTOA在观察覆盖、完整平仓清理、固定数据窗口及多空镜像上存在不一致行为
tags: [autobn, autoa, observation, oi, kline, window, partial-close]
---

# 策略状态与数据窗口不一致 Issue Report

## 1. 问题现象

当前交易流程存在多项可稳定观察到的不一致：

- 新的 BZ 观察条件成立时，可能因旧 Observation 含 BD 或同轮 BD 删除标记而无法覆盖旧记录；
- BZ Observation 有效期和完整平仓后的冷却均为24小时，完整平仓后仍保留该记录并写冷却，没有可复用窗口；
- BD 请求30条已完成日 OI 后，只取最后29条再拼最新5分钟 OI，第一条返回数据未参与实时窗口；
- AUTOBN SHORT 部分止盈后，余仓的止盈价被写到当前价上方、止损价被写到当前价下方，与空头方向相反；
- AUTOBN 多个固定 limit 的行情请求在返回数量不足时仍可能继续计算；
- AUTOA 行情不足30根时没有在统一入口终止，后续仍分散进行局部数据长度判断；
- 多头占比推导保留了实际接口不可能出现的 `longShortRatio <= -1` 分支。

## 2. 复现步骤

1. 构造一个已有 BD Observation、但本轮满足 BZ 观察条件的 AUTOBN 标的，执行 `rzq_token()`；观察新 BZ 可能未覆盖旧 BD。
2. 构造 BZ 完整平仓且交易所确认余仓为0；观察 Observation 被保留并写入24小时冷却，而其自身也将在24小时后过期。
3. 让 BD 日 OI 接口返回完整30条，再提供一条新鲜5分钟 OI；观察实时窗口丢弃第一条日 OI。
4. 构造 SHORT 止盈70%后仍有余仓且 ATR 大于0；观察余仓 TP/SL 方向反置。
5. 分别让 AUTOBN 固定请求30条的日K、OI或1小时多空比只返回29条；观察部分路径仍可能继续进入指标判断。
6. 让 AUTOA 合成行情少于30根；观察流程进入后续分支并在局部再次判断成交量长度。

复现频率：稳定。

## 3. 期望 vs 实际

**期望行为**：本轮新的真实 Observation 应直接覆盖旧记录，同轮 BZ 与 BD 同时成立时 BZ 优先；AUTOBN BZ/BD 确认完整平仓后均删除 Observation；BD 日 OI 固定请求30条并完整使用全部30条，再追加最新5分钟 OI；SHORT 部分止盈后余仓 TP/SL 与 LONG 方向镜像；AUTOBN 固定请求 N 条的数据少于 N 条时立即停止；AUTOA K线不足30根时在行情入口统一停止，后续不重复判断数据量。

**实际行为**：旧 Observation 和同轮删除标记会阻挡新观察覆盖；BZ完整平仓仍保留24小时Observation并写24小时冷却；BD实时OI窗口只保留29条日OI；SHORT余仓TP/SL反置；固定请求存在短窗口继续计算；AUTOA的数据量门槛分散在后续流程。

## 4. 环境信息

- 涉及模块 / 功能：AUTOBN BZ/BD 观察、开平仓与行情窗口；AUTOA 行情入口
- 相关文件 / 函数：`tokenDemo/autoTrade_pm.py` 中 `rzq_token()`、`_handle_closed_position_observation()`、`_get_bd_oi_windows()`、`check_side()`、`close_bn_position()`、AUTOA `on_observations()` / `on_positions()` 行情入口
- 运行环境：当前 `dev` 分支，Windows 11，Python 3.14，uv
- 其他上下文：用户明确只修改 `autoTrade_pm.py` 这一实现，不同步旧版 `autoTrade.py` / `autoTrade_papi.py`；同轮新候选维持 BZ 优先；固定数量规则覆盖 AUTOBN，AUTOA只增加统一30根K线入口门槛。

## 5. 严重程度

**P1** — 问题会改变候选策略方向、OI统计窗口以及部分平仓后的风控方向，并允许不完整固定窗口参与交易判断，直接影响开平仓状态正确性。

## 备注

本问题包含多个相互关联的状态和窗口一致性现象，需走标准 issue 流程分析根因并统一修复；不采用快速通道。
