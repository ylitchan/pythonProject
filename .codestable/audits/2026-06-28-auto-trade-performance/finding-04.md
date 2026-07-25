---
doc_type: audit-finding
id: F-04
nature: performance
severity: P2
confidence: medium
suggested_action: cs-refactor
source: tokenDemo/autoTrade_pm.py
---

# F-04 AUTOA 每轮监控无条件触发 gc.collect

## 证据

`AUTOA._monitor_stocks_impl()` 在每轮批次任务结束后无条件执行：

```python
if tasks:
    await asyncio.gather(*tasks)
gc.collect()  # 垃圾回收，释放内存
```

位置：`tokenDemo/autoTrade_pm.py:3336`

## 为什么是问题

`gc.collect()` 是全局强制垃圾回收，会暂停当前解释器执行。监控任务周期性运行时，每轮都强制 GC 可能引入稳定的尾延迟。这里没有看到基于内存阈值、批次数量、异常恢复等条件判断，因此可能是过度防御。

## 影响

- 每轮 A 股监控结束时产生额外停顿。
- 标的多、DataFrame 多时，强制 GC 成本可能更明显。
- 如果调度频率较高，会形成周期性 CPU 抖动。

## 建议

走 `cs-refactor`：

1. 默认移除无条件 `gc.collect()`，交给 Python 自动 GC。
2. 如果曾经有内存问题，改为条件触发，例如每 N 轮、内存超过阈值、或收盘全量处理后触发。
3. 用日志记录 GC 前后耗时和对象数量，确认是否真的收益大于成本。