---
doc_type: feature-ff-note
feature: mirror-short-basis-gate
date: 2026-07-25
requirement:
tags: [autobn, basis-rate, open-signal]
---

## 做了什么

AUTOBN 开空的基差率逻辑改成与开多镜像：删除 basis_rate <= 0（贴水）直接放弃开空的硬门槛，基差率不再拦截空头入场；Basis 标签从"过门槛后无条件打"改为仅在 basis_rate > +2%（BASIS_RATE_THRESHOLD）显著升水时追加。至此多空两侧基差率均只影响标签归因，不再是入场条件。

## 改了哪些

- tokenDemo/autoTrade_pm.py:2043-2046（rzq_token 空头分支）— 删除 `if basis_rate <= 0: return`，无条件 `strategy.append(Basis)` 改为 `if basis_rate > self.BASIS_RATE_THRESHOLD` 条件打标

## 怎么验证的

`uv run python -m py_compile` 编译通过；`uv run python -m unittest tokenDemo.test_autoTrade_pm` 46 个测试全部通过。

## 顺手发现（可选，不阻塞）

无。
