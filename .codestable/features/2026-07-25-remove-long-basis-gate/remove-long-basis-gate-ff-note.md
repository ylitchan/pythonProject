---
doc_type: feature-ff-note
feature: remove-long-basis-gate
date: 2026-07-25
requirement:
tags: [autobn, basis-rate, open-signal]
---

## 做了什么

AUTOBN 开多信号去掉基差率入场门槛：原先期货升水（basis_rate >= 0）时直接放弃开多，现在基差率不再拦截多头开仓。保留 basis_rate < -2%（BASIS_RATE_THRESHOLD）时给策略追加 Basis 标签的逻辑，用于消息与平仓记录归因。空头分支的基差率门槛（basis_rate <= 0 拒绝开空）保持不变。

## 改了哪些

- tokenDemo/autoTrade_pm.py:2004-2008（rzq_token 多头分支）— 删除 `if basis_rate >= 0: return` 两行，仍调用 get_basis_rate 取值（消息展示、Position.basis_rate 记录、Basis 标签判断继续使用）

## 怎么验证的

`uv run python -m py_compile` 编译通过；`uv run python -m unittest tokenDemo.test_autoTrade_pm` 46 个测试全部通过。

## 顺手发现（可选，不阻塞）

- tokenDemo/autoTrade_pm.py:2452 — AUTOA 类体在 import 时直接 `json.load(open("alert_all_A.json"))`，该文件被 gitignore，新环境缺文件时连测试都无法 import；本次从 .bak 恢复了 alert_all_A.json / alert_all.json 才能跑测试。建议改为惰性加载或缺失时给默认结构。
