---
doc_type: audit-finding
id: F-05
nature: performance
severity: P2
confidence: medium
suggested_action: cs-refactor
source: tokenDemo/autoTrade_pm.py
---

# F-05 AUTOBN 持仓检查中部分网络数据可并发预取

## 证据

`AUTOBN.rzq_token()` 每个 symbol 先拉日 K：

```python
kline = await self.get_kline(semaphore, symbol, "1Dutc")
```

位置：`tokenDemo/autoTrade_pm.py:1570`

持仓未触发普通止盈/止损时，可能继续顺序获取 5m OI：

```python
oi_5m = await self._get_oi_5m_data(symbol)
```

位置：`tokenDemo/autoTrade_pm.py:1658`

如果没有 OI 止损，又继续获取多空比：

```python
long_short_ratio_data = await self.get_long_short_ratio(symbol)
```

位置：`tokenDemo/autoTrade_pm.py:1665`

`get_long_short_ratio()` 内部命中/刷新 1h 多空比后，还会额外请求 5m 多空比：

```python
data2 = await self._call_api(
    self.market_client.rest_api.long_short_ratio,
    symbol=symbol,
    period="5m",
    limit=1,
)
```

位置：`tokenDemo/autoTrade_pm.py:1337`

## 为什么是问题

持仓检查属于高优先级热路径。当前代码为了避免不必要调用做了条件分支，这是合理的；但在“未触发价格止盈止损、且需要检查 OI/多空比”的路径里，网络请求是顺序等待的。对于持仓 symbol，OI 和多空比数据相互独立，可以在确认需要二级风控检查后并发预取，减少单标的尾延迟。

## 影响

- 单个 symbol 的风控检查耗时等于多个外部 API 的串行耗时之和。
- 多持仓时容易拉长整批 `asyncio.gather(*tasks)` 的尾部完成时间。
- 网络抖动时尾延迟更明显。

## 建议

走 `cs-refactor`：

1. 保留“先判断价格止盈/止损”的短路逻辑。
2. 当确认需要二级风控检查时，用 `asyncio.gather()` 并发拉取 OI 与多空比。
3. 对多空比 5m 最新值增加短 TTL 缓存，避免每次 `get_long_short_ratio()` 都额外请求 5m。