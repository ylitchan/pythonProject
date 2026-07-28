---
doc_type: issue-fix
issue: 2026-07-28-daily-cache-locks-stale-series
status: fixed
severity: P1
summary: 1d OI/多空比缓存无条件写入，跨UTC零点遇发布延迟会把过期序列锁定一整天
tags: [autobn, bz, cache, open-interest, long-short-ratio]
---

## 根因

commit `8af7b901` 把 BZ 路径从 1h 迁到 1d 时，丢掉了 1h 时代 `_get_oi_1h_data` 里「末根时间戳对齐当前周期边界才写缓存」这层保护。

迁移后 `_get_oi_1d_data`（`autoTrade_pm.py:1047`）和 `_get_lsr_1d_data`（`:1245`）只要过滤后凑够 30 根就无条件写缓存，而缓存键是 `target_date = 当天UTC零点`。币安这两个接口的末根时间戳就是当前周期的收盘时刻（口径见 `compound/2026-07-28-bn-oi-lsr-only-closed-periods.md`），跨过 UTC 零点后到币安发布当日那根之前有一段空窗期——这段时间内首次刷新拿到的末根还停在昨天零点，却被按今天的键写进缓存，**整整一天都读不到新数据**。周期从 1h 变 1d 让同一个漏洞的代价从 1 小时涨到 24 小时。

`_get_lsr_1d_data` 的 `except` 分支还会拿隔日旧缓存兜底，同样把过期序列喂给下游 blend 判断。

## 修了什么

按「不对齐就没缓存 + 直接判条件不成立」两条：

- `autoTrade_pm.py:1073-1075`（`_get_oi_1d_data`）— 凑够 30 根后加一道 `末根时间戳 == 当天UTC零点` 校验，不等就 `return None`，缓存不写。
- `autoTrade_pm.py:1278-1280`（`_get_lsr_1d_data`）— 同一道校验，不等就 `return []`，缓存不写。
- `autoTrade_pm.py:1268`（`_get_lsr_1d_data` 的 `except`）— 拉取失败从「回退隔日旧缓存」改成 `return []`，不再用陈旧数据兜底。

三处都是"失败关闭"：返回空/None 让 `check_side` 的 BZ 判断直接不成立，同时因为没写缓存，下一分钟的调用会重新走 API 拿币安已补发的那根。

## 怎么验证的

`uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py` 通过；`uv run python -m unittest discover -s tokenDemo -p "test_autoTrade_pm.py"` 96 项 OK。

新增/改写三个用例：

- `test_daily_oi_rejects_and_skips_cache_when_newest_bar_lags` — 末根停在昨天零点 → `None` 且 `_oi_1d_cache` 为空；第二次调用（币安已补发）拿到 30 根，断言 `await_count == 2` 钉住"确实重新走了 API"。
- `test_lsr_1d_rejects_and_skips_cache_when_newest_bar_lags` — 多空比侧同构，返回 `[]` 且不入缓存。
- `test_lsr_1d_returns_empty_on_api_error_without_stale_fallback` — 取代原 `test_lsr_1d_falls_back_to_stale_cache_on_api_error`，断言拉取失败返回 `[]`（仍记 error 日志）。

三次反向变异各自回滚验证测试非假绿：抹掉 OI 侧校验（挂 1）、抹掉多空比侧校验（挂 1）、把陈旧缓存兜底加回 `except`（挂 1）。

回归面：`test_daily_oi_uses_utc_availability_boundary` 与 5m 新鲜度、`AutoBNLongSignalTest` 五个 blend 用例全部原样通过——新校验只在末根滞后时生效，正常路径的末根本来就等于当天零点。

## 顺手发现

- 两条 1d 序列现在都保证「末根 == 当天UTC零点」才返回，`check_side` 里按时间戳定位区间末根这层对齐从"靠约定"变成了"被两侧共同的前置条件保证"，但仍没有断言把这个不变式钉在调用点。不在本次修复范围。
