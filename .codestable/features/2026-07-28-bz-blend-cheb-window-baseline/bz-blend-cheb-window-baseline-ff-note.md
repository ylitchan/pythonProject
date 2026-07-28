---
doc_type: feature-ff-note
feature: bz-blend-cheb-window-baseline
date: 2026-07-28
requirement:
tags: [autobn, bz, blend, long-short-ratio, cache]
---

## 做了什么

> 其中的 1h 周期与整点键控部分已被 `2026-07-28-bz-lsr-oi-daily-period` 取代（改用 1d + UTC 日边界）；「OI 取区间均值」已被 `2026-07-28-bz-blend-window-end-oi` 取代（改取区间末根那一根）。只有「多仓比例取区间末根」这条仍然有效。

AUTOBN BZ 做多的 blend 基准从「当前整点那一根」改成「切比雪夫区间（前 20 根 1h）」：OI 取该区间均值，多仓比例取该区间**最后一根**的值。blend 是 BZ 唯一的多空比开仓闸（见 `2026-07-26-remove-bz-raw-ratio-gates`），改成区间口径后不再被单根整点的抖动带偏。

配套把多空比缓存从 900 秒 TTL 改成按整点键控，与 1h OI 缓存同口径——两条序列要逐位对齐才能取「区间最后一根」，TTL 键控会在跨整点时让多空比落后 OI 一根。

## 改了哪些

- `autoTrade_pm.py:1178-1228`（`check_side` LONG 分支）— 平均 OI 用 `sumOpenInterest_1h[:-10]`，多仓比例用 `long_short_ratio_data[:-1][:-10][-1]`（先剔尾部那根 5m 再切区间）；删掉原来按时间戳精确匹配 + `<=` 回退的两段查找和其后不可达的 None 判断；`stop_guard_threshold` 复用 `avg_oi_1h`，不再重算同一个均值。
- `autoTrade_pm.py:1280-1307`（`get_long_short_ratio`）— 缓存键 `timestamp` → `target_date`（当前整点毫秒），仅当 1h 末根时间戳等于当前整点才写缓存；5m 那根仍不入缓存、每次实拉。
- `autoTrade_pm.py:311` — 删除已无引用的 `LONG_SHORT_RATIO_CACHE_TTL`（`autoTrade.py` / `autoTrade_papi.py` 各自的同名常量不受影响）。
- `test_autoTrade_pm.py` — 重写 `AutoBNLongSignalTest` 夹具为 30 根 OI / 31 项多空比（区间外填诱饵值），新增 `test_long_signal_blend_uses_cheb_window_avg_oi_and_ratio`；`test_cached_hour_ratio_still_requests_five_minute_ratio` 改用整点键，新增 `test_previous_hour_cache_triggers_hour_ratio_refetch`、`test_unaligned_hour_ratio_is_not_cached`。

## 怎么验证的

`uv run ruff check` 通过；`uv run python -m unittest discover -s tokenDemo -p "test_autoTrade_pm.py"` 91 项 OK。五次反向变异各自回滚验证测试非假绿：全窗口均值（2 挂）、取最新多空比而非区间末根（1 挂）、区间切片差一位（2 挂）、缓存无条件写入（1 挂）、缓存命中不校验整点（1 挂）。

## 顺手发现

- `_close_triggered_position:1557` 是多空比的第二个消费者，但只读 `[-1]["longShortRatio"]`（那根 5m），30 根 1h 对它是纯浪费——缓存未命中时会连带触发一次 1h 拉取。不在本次范围。
- `_get_oi_1h_data:1063` 与本次的多空比缓存都遵守「末根不对齐当前整点就不写缓存」，因此两条序列各自都可能滞后一根；只要两边同时滞后就仍逐位对齐，但这个不变式目前只靠约定，没有断言兜底。
