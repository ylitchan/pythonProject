# 币安 OI 与多空比接口只返回已走完的周期

## 背景

把 AUTOBN BZ 做多路径从 1h 换成 1d 时，我在 ff-note 里写了条顺手发现，说 `_get_oi_1d_data` 的可得边界 `timestamp <= 当天UTC零点` 会含进「当天那根未走完的日线」。这是拿 K 线的直觉套到了统计类接口上，判断错了。

## 结论

**`openInterestHist`（OI 历史）和 `longShortAccountRatio`（多空人数比）跟 K 线不是一回事：不管 period 传 5m / 1h / 1d，返回的最新一根永远是已经走完的上一个周期，不存在进行中的当期数据。**

由此推出两条：

1. **不需要「剔除未完成那根」的过滤**。按周期边界过滤 `timestamp <= 边界` 对这两个接口是恒真的空操作，不是安全网。要判断数据够不够新，得反过来断言「末根等于上一个周期的起点」。
2. **周期越长，新数据的到达越值得防**。1d 数据在整个 UTC 日内都不会变（末根固定是昨天那根），所以按 UTC 日键控缓存是对的；但跨过 UTC 零点后币安发布昨天那根有延迟，此时若无条件写缓存，会把「末根停在前天」的序列锁定一整天。1h 时代的写法是 `if oi_1h[-1]["timestamp"] == 当前整点: 写缓存`，正是为了防这个——迁移到 1d 时这层保护没跟着搬过来。

K 线（`kline_candlestick_data`）不受此结论约束，它确实会返回进行中的当期。

## 证据

- 用户口头确认（2026-07-28）：「oi和多空比，不管是啥周期的，bn都只能看到前一个周期，这些数据和k线不一样，不存在没走完的数据」。
- 被此结论推翻的错误记载：`.codestable/features/2026-07-28-bz-lsr-oi-daily-period/bz-lsr-oi-daily-period-ff-note.md` 的「顺手发现」节（已订正）。
- 相关实现：`tokenDemo/autoTrade_pm.py` 的 `_utc_day_start_ms` / `_get_oi_1d_data` / `_get_lsr_1d_data`。
- 被移除的 1h 时代保护写法：见 commit `8af7b901` 里 `_get_oi_1h_data` 的删除 diff。
