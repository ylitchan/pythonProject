---
doc_type: issue-fix
issue: 2026-07-28-5m-cache-ttl-stale-window
status: fixed
severity: P1
summary: AUTOBN 四条行情缓存（OI/多空比 × 5m/1d）统一成"末根时间戳单调推进"协议，取用一律读缓存
tags: [autobn, bz, bd, cache, open-interest, long-short-ratio]
---

## 根因

`_get_oi_5m_data` 的缓存 `TTL = OI_5M_CACHE_TTL = 300` 秒，**从取数时刻起算**，而 300 秒恰好等于一个 5m 周期。这两条叠加就能 serve 近两倍周期的陈旧数据：某次取数拿到的 bar 已经 4:59 岁，这条缓存还要再活 4:59 才过期——最后一刻读到的 bar 年龄接近 10 分钟，整整落后一个周期。

`_get_lsr_5m_data` 反过来完全不缓存，每次实拉并硬编码 `5*60` 按**末根时间戳**判新鲜度，年龄严格 ≤5 分钟。两个同周期方法形态相反，于是 blend 的两个输入不同龄：`oi_5m_last` 最旧可 ~10 分钟，`long_ratio_5m` 保证 ≤5 分钟。

三个消费者里只有 `_get_bd_oi_windows` 在下游自己按末根时间戳补了一道 age 校验兜底；`check_side` 的 BZ LONG 分支和 `_close_triggered_position` 都直接吃缓存返回值，没有任何校验。

顺带一个浪费：`_get_oi_5m_data` 拉 `limit=OI_QUERY_LIMIT`（30 根），但三个消费者全都只读 `[-1]`，另外 29 根纯属白拉。

## 修了什么

四条行情缓存（OI / 多空比 × 5m / 1d）统一成同一套**末根时间戳单调推进**协议：

1. 缓存末根时间戳 == 当前时刻能拿到的最新那根 → 直接返回缓存，不打 API
2. 否则拉一次，比缓存末根和拉回末根的时间戳，**严格更新的那份才替换缓存**
3. 取用一律返回缓存——不因为末根滞后就把数据判掉

唯一的周期差异是第 1 步"能拿到的最新"怎么算：5m 是 `floor(now/300s)*300s`，1d 是当天 UTC 零点（币安这两个接口只返回已走完周期，且时间戳是收盘时刻，见 `compound/2026-07-28-bn-oi-lsr-only-closed-periods.md`）。

- `autoTrade_pm.py:313` — `OI_5M_CACHE_TTL` → `FIVE_MIN_PERIOD_MS = 300_000`，语义从"缓存活多久"变成"5m 周期长度"，只用来算当期边界。`autoTrade.py` / `autoTrade_papi.py` 各自的同名常量不受影响。
- `autoTrade_pm.py:1013-1043` — 三个共享 helper：`_bar_timestamp_ms`（秒/毫秒兼容）、`_is_current_5m_bar`（是否已是当期那根，只决定要不要打 API）、`_is_newer_bar`（值不值得换缓存）。
- `autoTrade_pm.py:1045-1059`（`_get_oi_5m_data`）— 按新协议重写；`limit` 30→1；缓存条目从 `{"data": [...], "timestamp": float}` 简化成裸 list。
- `autoTrade_pm.py:1069-1093`（`_get_oi_1d_data`）— 同协议；缓存条目从 `{"data": [...], "target_date": int}` 简化成裸 list，不再存缓存键。
- `autoTrade_pm.py:1252-1285`（`_get_lsr_1d_data`）— 同协议。
- `autoTrade_pm.py:1287-1308`（`_get_lsr_5m_data`）— 新增 `_lsr_5m_cache`，同协议。
- `autoTrade_pm.py:484-487` — `__new__` 四个缓存统一口径初始化。
- `autoTrade_pm.py:1096-1098`（`_get_bd_oi_windows`）— 删掉下游那 7 行重复的 age 校验。

两处 1d 的 `len(...) >= LIMIT` 判据保留，但语义从"要不要接受这份数据"变成"要不要用它替换缓存"——不足 30 根的短序列顶不掉已有的好缓存。

两处多空比的 `except` 分支从 `return []` 改成 `return 缓存 or []`：拉取失败就是没有新数据可比，按协议第 3 条照用缓存。**这一条反转了本 issue 早期版本"拉取失败不拿隔日旧缓存顶"的口径**，是用户明确要求的结果。

## 怎么验证的

`uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py` 通过；`uv run python -m unittest discover -s tokenDemo -p "test_autoTrade_pm.py"` 110 项 OK。

用例覆盖四个方法 × 协议三步，每步都有对应断言：

- 第 1 步不打 API：`test_lsr_5m_skips_api_when_cache_is_current_bar` / `test_oi_5m_matches_lsr_5m_cache_protocol`（同时钉 `limit=1`）/ `test_lsr_1d_uses_cache_when_last_bar_is_utc_day_start` / `test_daily_oi_uses_cache_when_last_bar_is_utc_day_start`。
- 第 2 步只换更新的：`test_*_keeps_cache_when_fetched_bar_is_not_newer`（5m 两个）/ `test_*_keeps_cache_when_fetched_series_is_not_newer`（1d 两个）/ `test_lsr_1d_refetches_after_utc_day_rollover`。
- 第 3 步一律返回缓存：`test_*_returns_cache_when_response_is_empty`、`test_lsr_1d_falls_back_to_cache_on_api_error`、以及无缓存时的 `test_lsr_5m_returns_empty_when_never_cached` / `test_oi_5m_returns_none_when_never_cached` / `test_lsr_1d_returns_empty_on_api_error_without_cache`。
- 滞后序列先用后换：`test_lsr_1d_caches_lagging_series_then_swaps_in_newer` / `test_daily_oi_caches_lagging_series_then_swaps_in_newer`（`await_count == 2`）。
- 短序列不入缓存：`test_lsr_1d_drops_bars_after_utc_day_start` / `test_daily_oi_drops_bars_after_utc_day_start`。
- helper 边界：`test_is_current_5m_bar_matches_period_boundary_exactly`（严格等于当期边界，`+1` 判否、秒级换算、缺时间戳判否）/ `test_is_newer_bar_compares_timestamps`。

5m 夹具一律用真实对齐值（300 秒整数倍）——早先版本用了 699/700/900 这类非对齐时间戳，测的是生产里不存在的状态。

**14 次反向变异各自回滚验证测试非假绿**：抹掉四个方法的当期判据（各挂 1）、抹掉四个方法的 `_is_newer_bar` 闸（各挂 1）、抹掉两处 1d 的 `len >= LIMIT` 闸（各挂 1）、四个方法末尾返回拉取值而不是缓存（各挂 2）、多空比异常路径不回退缓存（挂 1）。首轮跑出两处假绿（1d OI 缺"当期就不拉"和"短序列不入缓存"的用例），补齐后全部命中。

回归面：`_close_triggered_position` 的 OI 止损护栏路径、BZ LONG blend 五个用例全部原样通过。

## 顺手发现

- `_get_oi_5m_data` / `_get_oi_1d_data` 没有 `try/except`，两个多空比方法有——OI 侧 `_call_api` 抛异常时会往上冒，拿不到"回退缓存"这层保护。本次只统一缓存协议，异常处理不在范围内，可后续另开 issue。
- 四条缓存现在都是"只增不减、末根单调推进"，没有淘汰：`_call_api` 长期失败时策略会一直拿最后一次成功的数据算，且下游不再有任何新鲜度否决。这是用户选定口径的直接后果，不是缺陷——但如果以后要加"太旧就别算了"的护栏，位置应该在消费者侧而不是取数侧。
