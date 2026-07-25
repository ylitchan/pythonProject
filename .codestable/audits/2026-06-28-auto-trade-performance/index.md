---
doc_type: audit-index
status: active
title: autoTrade_pm 平仓与监控性能审计
scope:
  - tokenDemo/autoTrade_pm.py
focus:
  - AUTOBN 平仓/监控逻辑
  - AUTOA 平仓/监控逻辑
  - CloseRecordManager 平仓记录写入
created_at: 2026-06-28
---

# autoTrade_pm 平仓与监控性能审计

## 范围

- 文件：`tokenDemo/autoTrade_pm.py`
- 重点：`AUTOBN` / `AUTOA` 的平仓与监控逻辑
- 维度：performance
- 本次只发现问题与优化点，不直接修改代码。

## 总评

当前代码已经做了一些有价值的性能控制：

- AUTOBN / AUTOA 都有分批窗口，避免每分钟全量扫描。
- 外部 API 调用有并发信号量限制。
- AUTOBN 对多空比、OI、基差率有部分缓存。
- AUTOA 对历史行情有 `hist_cache`。

主要性能瓶颈集中在三类：

1. **平仓记录写 Excel 每次全量读写 workbook**：平仓高频或多策略同时触发时会明显放大 I/O。
2. **AUTOA 同一批次内同一股票历史行情可能重复拉取/处理**：持仓与观察逻辑各自调用 `stock_zh_a_hist`，缓存只覆盖历史日 K，不覆盖当天分时聚合，热点路径仍会重复请求新浪分时接口。
3. **批量监控路径里存在不必要的全局 GC 与串行收盘处理**：会拖慢每轮监控，尤其 A 股涨停池较大时。

## 发现清单

| ID | 性质 | 严重度 | 置信度 | 建议动作 | 摘要 |
|---|---|---|---|---|---|
| F-01 | performance | P1 | high | cs-refactor | 每次平仓记录都会全量读写 Excel 所有 sheet，I/O 随记录增长持续放大 |
| F-02 | performance | P1 | high | cs-refactor | AUTOA `stock_zh_a_hist` 缓存不覆盖当天分时聚合，持仓/观察批次会重复请求与重建 DataFrame |
| F-03 | performance | P2 | medium | cs-refactor | AUTOA 收盘更新涨停池逐只串行拉行情，涨停数量多时容易吃满监控窗口 |
| F-04 | performance | P2 | medium | cs-refactor | AUTOA 每轮批次结束无条件 `gc.collect()`，可能造成周期性停顿 |
| F-05 | performance | P2 | medium | cs-refactor | AUTOBN 同一 symbol 在持仓检查中可能顺序触发多次网络调用，可合并/并发预取部分数据 |

## 交叉分类矩阵

| 严重度 \\ 性质 | performance |
|---|---:|
| P0 | 0 |
| P1 | 2 |
| P2 | 3 |

## 下一步建议

1. 优先处理 **F-01**：平仓路径是关键路径，Excel 全量读写会随着记录增长越来越慢。
2. 然后处理 **F-02**：AUTOA 监控频繁运行，同一批次重复拉取当天分时是稳定的外部 I/O 成本。
3. F-03/F-04/F-05 可以作为下一轮性能重构一起做。

如果要开始改，建议用 `cs-refactor`，先做 F-01 或 F-02。