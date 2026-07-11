---
doc_type: issue-fix
issue: 2026-07-11-autoa-daily-calendar-reuse
status: fixed
severity: P2
summary: AUTOA 每日持仓通知复用单次交易日期快照，避免按持仓重复请求交易日历
tags: [autoa, daily-position, performance]
---

# AUTOA 日报交易日历复用 Fix Note

## 问题与目标

AUTOA 每日持仓通知在 `zt_dates` 尚未初始化时，每只持仓的行情查询都会单独获取一次相同交易日历。持仓越多，重复外部请求和通知生成延迟越明显。

期望行为：一次日报只获取一次交易日期快照，所有持仓复用；每只股票的实时行情仍独立请求，不缓存或跨标的复用价格。

## 修复

- `AUTOA.push_daily_positions()` 在遍历持仓前取得一次交易日期快照。
- `AUTOA._get_auction_price()` 改为显式接收该快照，不再自行请求交易日历。
- 股票行情请求保持逐只调用，实时性边界不变。

## 验证

- 两只持仓且 `zt_dates` 为空时，`get_last_trading_days()` 只调用一次。
- 两只持仓均收到同一份日期快照。
- `_get_auction_price()` 对不同股票仍分别调用行情接口，共调用两次。
- 无持仓时仍直接发送空仓通知，不请求交易日历。

测试命令：

```text
uv run python -m unittest tokenDemo.test_autoTrade_pm.AutoADailyPositionValuationTest
```

结果：6 项测试全部通过。

## 影响范围

仅调整 AUTOA 每日持仓通知的交易日历获取位置。交易策略、实时股票行情、AUTOBN 和通知文本均未修改。

## 遗留

无。
