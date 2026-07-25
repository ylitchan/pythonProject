---
doc_type: audit-finding
id: F-03
nature: performance
severity: P2
confidence: medium
suggested_action: cs-refactor
source: tokenDemo/autoTrade_pm.py
---

# F-03 AUTOA 收盘更新涨停池逐只串行拉行情

## 证据

收盘时获取涨停池后，代码逐只股票 `await cls.stock_zh_a_hist(...)`：

```python
stock_codes = zt_df[["代码", "名称", "连板数"]].values.tolist()
for code in stock_codes:
    try:
        hist = await cls.stock_zh_a_hist(
            code[0],
            ...
        )
```

位置：`tokenDemo/autoTrade_pm.py:3240`

## 为什么是问题

这里没有使用并发信号量，也没有批量 gather。涨停池数量较多时，收盘更新观察列表会变成 N 次串行网络请求 + DataFrame 处理。虽然只在收盘阶段执行，但它仍处在 `_monitor_stocks_impl()` 内，外层有 `MONITOR_TIMEOUT = 55` 秒限制。

## 影响

- 涨停池数量大时，收盘更新可能明显变慢。
- 单个慢请求会阻塞后续所有股票。
- 可能导致观察列表更新不完整或任务超时。

## 建议

走 `cs-refactor`：

1. 使用 `asyncio.Semaphore(cls.MAX_CONCURRENT_REQUESTS)` 控制并发。
2. 将逐只处理拆为 `_process_zt_stock(code)`，用 `asyncio.gather()` 并发执行。
3. 对失败单票保留现有容错，避免一个异常影响整体。