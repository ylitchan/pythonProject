---
doc_type: audit-finding
id: F-02
nature: performance
severity: P1
confidence: high
suggested_action: cs-refactor
source: tokenDemo/autoTrade_pm.py
---

# F-02 AUTOA 行情缓存不覆盖当天分时聚合

## 证据

`AUTOA.stock_zh_a_hist()` 对历史日 K 做了 `hist_cache`：

```python
if code in cls.hist_cache:
    hist = cls.hist_cache[code].copy()
else:
    ...
    cls.hist_cache[code] = hist.copy()
```

位置：`tokenDemo/autoTrade_pm.py:2786`、`tokenDemo/autoTrade_pm.py:2831`

但即使命中缓存，函数后半段仍会每次请求新浪分时数据：

```python
async with http_session.get(
    url=f"https://cn.finance.sina.com.cn/minline/getMinlineData?symbol={code_pre}{code}",
    headers=headers,
) as response:
    payload = await response.json(content_type=None)
    res = payload.get("result", {}).get("data", [])
```

位置：`tokenDemo/autoTrade_pm.py:2839`

然后每次都重新构造当天 DataFrame 并 concat：

```python
hist_today = pd.DataFrame(res)
...
hist = pd.concat([hist, today_row], ignore_index=True)
```

位置：`tokenDemo/autoTrade_pm.py:2853`、`tokenDemo/autoTrade_pm.py:2889`

这个函数在持仓平仓检查和观察买入检查都会调用：

- `AUTOA.on_positions()`：`tokenDemo/autoTrade_pm.py:2918`
- `AUTOA.on_observations()`：`tokenDemo/autoTrade_pm.py:3105`

## 为什么是问题

A 股监控是周期性任务，同一股票在一个 5 分钟窗口内可能被重复处理。当前缓存只避免重复拉历史日 K，但没有缓存“历史日 K + 当天分时聚合后的完整 hist”。所以热点成本仍然存在：

- 每次请求新浪分时接口。
- 每次解析 JSON。
- 每次构造 `hist_today` DataFrame。
- 每次 concat 一行当天聚合数据。

这些操作都是监控热路径，且受外部网络波动影响。

## 影响

- AUTOA 每轮监控外部 HTTP 请求数偏高。
- DataFrame 构造和 concat 在批量股票下增加 CPU/内存压力。
- 新浪接口慢或限流时，容易拖到 `MONITOR_TIMEOUT = 55` 秒。

## 建议

走 `cs-refactor`：

1. 增加短 TTL 的当天分时聚合缓存，例如 `{code: {minute_bucket, today_row}}`。
2. `stock_zh_a_hist()` 命中同一分钟/同一批次缓存时直接复用 `today_row`。
3. 或在 `_monitor_stocks_impl()` 的批次开始阶段按 `effective_symbols` 统一预取行情，传给 `on_positions` / `on_observations`。