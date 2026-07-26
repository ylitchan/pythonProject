---
doc_type: issue-fix
issue: 2026-07-26-strategy-state-window-consistency
status: completed
date: 2026-07-26
related: [strategy-state-window-consistency-report.md, strategy-state-window-consistency-analysis.md]
tags: [autobn, autoa, observation, oi, kline, window, partial-close]
---

# 策略状态与数据窗口一致性修复记录

## 修复内容

- AUTOBN 每轮直接按真实条件选择新 Observation：BZ 优先、BD 次之；新候选成立即覆盖旧记录，不再受旧BD、同UTC日或 `bd_deleted_this_round` 阻挡。
- AUTOBN完整平仓行为已由后续修复 `2026-07-26-bz-close-preserve-observation` 纠正：BZ保留Observation并只更新最早重开时间，BD删除Observation。
- 日OI固定请求30条，过滤后不足30条停止；BD实时窗口使用全部30条完成日OI加最新1条5m OI，baseline使用old之前的全部数据。
- 日K、5m/1h/1d OI、1h多空比和最新5m多空比在获取边界拒绝不完整窗口，短缓存也不再复用。
- SHORT部分止盈后直接采用方向化的 `(take_profit, stop_loss)`，保持TP在当前价下方、SL在当前价上方。
- AUTOA观察与持仓行情入口统一要求至少30根K线，删除后续2根/30根及成交量局部长度兜底。
- 删除不可能的 `longShortRatio <= -1` 防御分支。

## 修改范围

- `tokenDemo/autoTrade_pm.py` — 状态覆盖、完整平仓、固定窗口、BD OI、SHORT余仓和AUTOA入口逻辑。
- `tokenDemo/test_autoTrade_pm.py` — 更新完整窗口夹具，新增新旧Observation覆盖、BZ优先、AUTOBN 29/30边界、AUTOA 29根入口测试，并增强SHORT部分止盈断言。
- `.codestable/requirements/shared-observation-reopen-cooldown.md` — AUTOBN完整平仓统一删除Observation，AUTOA交易日冷却保持不变。
- 本issue的 report、analysis 与 fix-note。

## 验证结果

- `uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py`：通过。
- `uv run python -m unittest tokenDemo.test_autoTrade_pm`：85项测试通过，结果 `OK`。
- `git diff --check`：通过。
- 残留引用搜索确认 `bd_deleted_this_round`、`can_set_observation`、日OI 31条请求、29条日OI截断、`lsr <= -1`、SHORT TP/SL二次交换及AUTOA后续重复长度guard均已清理。
- 测试输出中的 `OSError: 文件被占用` 为既有 `CloseRecordManager` 错误恢复测试主动模拟的日志，不影响最终测试结果。

## 影响面回归

- AUTOBN BZ/BD观察有效期仍分别为24小时和7天，只有真实观察条件写入timestamp。
- AUTOBN开仓、DCA、ATR、Blend与OI止损既有测试保持通过。
- AUTOA N复用BZ Observation、完整平仓保留Observation并按A股交易日冷却的既有测试保持通过。

## 范围核对

未修改 `tokenDemo/autoTrade.py` 或 `tokenDemo/autoTrade_papi.py`；未带入用户已有 `.gitignore`、`tokenDemo/backtest_autoa.py`、`tokenDemo/test_backtest_autoa_parity.py` 及其他未跟踪CodeStable改动。未执行commit或push。
