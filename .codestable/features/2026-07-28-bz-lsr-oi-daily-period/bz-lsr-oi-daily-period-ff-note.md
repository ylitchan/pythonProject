---
doc_type: feature-ff-note
feature: bz-lsr-oi-daily-period
date: 2026-07-28
requirement:
tags: [autobn, bz, blend, long-short-ratio, open-interest, cache]
---

## 做了什么

AUTOBN BZ 做多路径彻底不再用 1h 周期：OI 和多空人数比都换成 1d。两条序列的缓存因此统一按 UTC 日边界过期，和已有的 1d OI 缓存同口径，不再有「整点键控 vs 15 分钟 TTL」两套过期语义。

多空比拉取按 OI 的样子拆成 `_get_lsr_1d_data`（30 根 1d，按 UTC 日缓存）和 `_get_lsr_5m_data`（1 根 5m，不缓存），blend 调用点相应改成分别取。顺带解决了两条 1d 序列各自独立刷新可能错位的问题：**区间末根的多仓比例按时间戳定位，不按下标切片**——对齐性来自数据本身，跟两边缓存什么时候刷新无关。切比雪夫区间末根距序列尾部还有 10 根，最多能容忍 20 根整体漂移；真取不到那根就直接不开仓（返回 False，不抛异常）。

取代 `2026-07-28-bz-blend-cheb-window-baseline` 里的 1h / 整点键控部分，blend 取切比雪夫区间均值这条口径不变。

## 改了哪些

- `autoTrade_pm.py:1039-1045` — 新增 `_utc_day_start_ms`，UTC 零点毫秒时间戳只算一处，两个 1d 拉取方法共用。
- `autoTrade_pm.py:1238-1276`（`_get_lsr_1d_data`，替代原 `get_long_short_ratio`）— 30 根 1d，`timestamp <= 当天UTC零点` 才算已可得，够 30 根才入缓存；拉取失败退回旧缓存（按时间戳取值，滞后一天也不错位）。
- `autoTrade_pm.py:1278-1301`（`_get_lsr_5m_data`）— 只拉 1 根 5m，5 分钟新鲜度校验保留，不入缓存。
- `autoTrade_pm.py:1126-1198`（`check_side` LONG 分支）— 改用 `_get_oi_1d_data` + 两个新多空比方法；`window_end_ts` 取 `oi_1d[-11]["timestamp"]`，多仓比例从 `{时间戳: 项}` 字典里查；删掉只用尾元素的 `lsr_values` 列表推导和恒不成立的 `len(sumOpenInterest_1h) < 1` 判断。
- `autoTrade_pm.py:1515-1526`（`_close_triggered_position` OI 止损闸）— 改调 `_get_lsr_5m_data`，不再为读一根 5m 顺带触发 30 根拉取（上一份 ff-note 的顺手发现，本次自然消解）。
- `autoTrade_pm.py:1036-1077` — 删除 `_get_oi_1h_data`；`autoTrade_pm.py:478-487` 删除 `_oi_1h_cache`、`_long_short_ratio_cache` 改名 `_lsr_1d_cache`。全文件已无 `1h` 相关残留符号。
- `test_autoTrade_pm.py` — `AutoBNLongSignalTest` 夹具改为带时间戳的 30 根 1d，新增 `lsr_lag_days` 参数模拟两条序列整体错位，新增按时间戳取值和缺失时静默拒绝两个用例；多空比缓存用例改按 UTC 日键控重写为 7 个。

## 怎么验证的

`uv run ruff check` 通过；`uv run python -m unittest discover -s tokenDemo -p "test_autoTrade_pm.py"` 94 项 OK。四次反向变异各自回滚验证测试非假绿：按下标切片取区间末根（挂 2）、均值用全窗口而非切比雪夫区间（挂 3）、缓存命中不校验 UTC 日（挂 2）、拉取后不过滤未来根（挂 1）。

## 顺手发现

- 1d 序列的缓存是无条件写的（过滤后够 30 根就写），但 OI / 多空比这两个接口最新一根永远是上一个已走完周期（见 `compound/2026-07-28-bn-oi-lsr-only-closed-periods.md`）。跨过 UTC 零点、币安还没发布昨天那根时刷新，会把末根停在前天的序列锁定一整天。1h 时代 `_get_oi_1h_data` 有「末根对齐当前整点才入缓存」这层保护，迁移时没跟着搬过来。不在本次范围，建议单独走 `cs-issue`。
