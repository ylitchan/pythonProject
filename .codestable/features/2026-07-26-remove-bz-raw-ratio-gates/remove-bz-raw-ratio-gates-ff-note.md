---
doc_type: feature-ff-note
feature: remove-bz-raw-ratio-gates
date: 2026-07-26
requirement:
tags: [autobn, bz, long-short-ratio, blend, risk-control]
---

## 做了什么
AUTOBN BZ 不再以原始多空人数比设置独立开仓门槛，也不再仅因持仓后的多空比偏高而直接平仓。多空比入场确认只保留 Blend，持仓阶段保留多空比参与确认的 OI 止损。

## 改了哪些
- `tokenDemo/autoTrade_pm.py:check_side` — 删除 `lsrd < 1.0` 的 BZ 开仓硬门槛及无用常量。
- `tokenDemo/autoTrade_pm.py:_close_triggered_position` — 删除 `latest_lsr >= 1.5` 的直接多空比止损及无用常量，保留 OI 止损。
- `tokenDemo/test_autoTrade_pm.py` — 新增高原始多空比下 Blend 放行/拒绝测试，并将高多空比直接止损测试改为不平仓回归测试。

## 怎么验证的
`uv run ruff check tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py` 通过；`uv run python -m unittest tokenDemo.test_autoTrade_pm` 共82项测试通过。

## 顺手发现
- `tokenDemo/autoTrade.py` 与 `tokenDemo/autoTrade_papi.py` 仍有旧的开仓门槛，但属于其他实现且不在本次用户指定范围，未修改。
