---
doc_type: issue-fix
issue: 2026-07-28-5m-cache-ttl-stale-window
status: fixed
severity: P1
summary: 5m OI 缓存 TTL 按取数时刻计时且恰好等于一个周期，最坏可返回近10分钟前的 bar，与同龄的 5m 多空比口径不一致
tags: [autobn, bz, bd, cache, open-interest, long-short-ratio]
---

## 根因

`_get_oi_5m_data` 的缓存 `TTL = OI_5M_CACHE_TTL = 300` 秒，**从取数时刻起算**，而 300 秒恰好等于一个 5m 周期。这两条叠加就能 serve 近两倍周期的陈旧数据：某次取数拿到的 bar 已经 4:59 岁，这条缓存还要再活 4:59 才过期——最后一刻读到的 bar 年龄接近 10 分钟，整整落后一个周期。

`_get_lsr_5m_data` 反过来完全不缓存，每次实拉并硬编码 `5*60` 按**末根时间戳**判新鲜度，年龄严格 ≤5 分钟。两个同周期方法形态相反，于是 blend 的两个输入不同龄：`oi_5m_last` 最旧可 ~10 分钟，`long_ratio_5m` 保证 ≤5 分钟。

三个消费者里只有 `_get_bd_oi_windows` 在下游自己按末根时间戳补了一道 age 校验兜底；`check_side` 的 BZ LONG 分支（`:1145`）和 `_close_triggered_position`（`:1540`）都直接吃缓存返回值，没有任何校验。

顺带一个浪费：`_get_oi_5m_data` 拉 `limit=OI_QUERY_LIMIT`（30 根），但三个消费者全都只读 `[-1]`，另外 29 根纯属白拉——`len(data) >= 30` 这条缓存有效性判据守的也正是这 29 根没人用的数据。

## 修了什么

按用户选定的「都缓存 + 都按末根时间戳校验」统一两个方法：

- `autoTrade_pm.py:313` — `OI_5M_CACHE_TTL` 改名 `FIVE_MIN_DATA_MAX_AGE`，语义从"缓存活多久"变成"末根允许多旧"，两个方法共用（多空比侧原先硬编码 `5*60`）。`autoTrade.py` / `autoTrade_papi.py` 各自的同名常量不受影响。
- `autoTrade_pm.py:1015-1025` — 新增 `_is_fresh_5m_bar` classmethod，消除两处新鲜度判断的重复，顺带统一秒/毫秒时间戳兼容。
- `autoTrade_pm.py:1027-1043`（`_get_oi_5m_data`）— 缓存命中也要过一遍新鲜度校验；`limit` 30→1；末根超龄返回 `None` 且**不写缓存**。缓存条目从 `{"data": [...], "timestamp": float}` 简化成裸 `[末根]`，不再存取数时刻。
- `autoTrade_pm.py:1287-1309`（`_get_lsr_5m_data`）— 新增 `_lsr_5m_cache`，同一套逻辑；末根超龄返回 `[]` 且不写缓存。
- `autoTrade_pm.py:488` — `__new__` 初始化 `_lsr_5m_cache`。
- `autoTrade_pm.py:1094-1096`（`_get_bd_oi_windows`）— 删掉下游那 7 行重复的 age 校验，新鲜度责任下沉一层，这里只需处理 `_get_oi_5m_data` 返回 `None`。

关键论证：**末根时间戳校验严格蕴含原 TTL 校验**（取数时刻 ≥ bar 时刻 ⇒ 取数年龄 ≤ bar 年龄），所以存取数时刻这个字段是纯冗余，删掉不损失任何约束，只收紧。

两处都是"失败关闭"：不新鲜就返回空/None 让上层条件直接不成立，同时因为没写缓存，下一分钟的调用会重新走 API 拿币安已发布的那根。

## 怎么验证的

`uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py` 通过；`uv run python -m unittest discover -s tokenDemo -p "test_autoTrade_pm.py"` 104 项 OK。

新增 8 个用例（`AutoBNCharacterizationTest`）：

- `test_lsr_5m_serves_fresh_cache_without_refetch` / `test_oi_5m_matches_lsr_5m_freshness_and_cache_shape` — 缓存确实生效（`await_count == 1`），后者同时断言 `limit=1`。
- `test_lsr_5m_refetches_when_cached_bar_ages_out` / `test_oi_5m_refetches_when_cached_bar_ages_out` — 缓存里的 bar 超龄要重拉，钉住"命中也校验"。
- `test_lsr_5m_stale_response_is_not_cached` / `test_oi_5m_stale_response_returns_none_and_is_not_cached` — 超龄响应不入缓存，下次仍走 API（`await_count == 2`）。
- `test_oi_5m_rejects_future_bar` — 时间戳超前于当前时钟判否，钉住 `0 <=` 下界。
- `test_five_min_freshness_accepts_millisecond_timestamps` — helper 的毫秒换算与边界（300s 放行、301s 判否、`timestamp` 缺失/为 None 判否）。

改写 2 个：`test_bd_oi_windows_reject_stale_or_future_5m` → `test_bd_oi_windows_reject_unavailable_5m`（原用例测的是已删除的下游校验）；`test_autobn_fixed_fetches_reject_29_and_accept_30` → `test_autobn_kline_rejects_29_and_accepts_30`（其 OI-5m 那一半断言的是已删除的 `len >= 30` 判据，K 线那一半仍有效）。

五次反向变异各自回滚验证测试非假绿：抹掉 OI 侧命中校验（挂 1）、抹掉多空比侧命中校验（挂 1）、去掉 `0 <=` 下界（挂 1）、抹掉 OI 拉取路径的新鲜度闸（挂 2）、去掉毫秒换算（挂 2）。

回归面：`_close_triggered_position` 的 OI 止损护栏路径、BZ LONG blend 五个用例全部原样通过——两个方法的正常路径（末根就是刚发布那根）返回值不变，改动只在超龄时生效。

## 顺手发现

- `_get_oi_5m_data` 没有 `try/except`，`_get_lsr_5m_data` 有——两个方法在异常处理上仍不对称，`_call_api` 抛异常时前者会往上冒。这次只统一缓存与新鲜度口径，异常处理不在范围内，可后续另开 issue。
