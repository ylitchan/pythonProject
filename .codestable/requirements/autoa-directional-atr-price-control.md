---
doc_type: requirement
slug: autoa-directional-atr-price-control
pitch: 让AUTOA保留盈利空间的同时独立收紧亏损边界
status: current
last_reviewed: 2026-08-03
implemented_by: []
tags: [autoa, risk-control]
---

# AUTOA 按风控职责管理 ATR 价格线

## 用户故事

- 作为运行AUTOA策略的人，我希望止盈空间和止损边界可以分别调整，而不是被同一个距离绑定。
- 作为交易执行者，我希望收紧止损时仍保留原有盈利空间。
- 作为策略维护者，我希望初始价格线和持仓动态轨道采用一致的职责口径。

## 为什么需要

统一的波动倍数会让止盈和止损被迫同步变化，无法在保留盈利空间的同时控制更近的亏损边界。

## 怎么解决

AUTOA分别设置盈利目标距离与亏损保护距离，并让新开仓价格线和持仓期间的动态轨道使用相同口径。已有有效价格线不会因版本发布而无条件迁移。

## 边界

- 只负责AUTOA的初始ATR价格线和动态轨道，不改变AUTOBN。
- 不改变ATR计算、DCA、成交量退出、盈利追踪或止盈衰减规则。
- 已有持仓的有效价格线继续沿用既有持仓管理流程。
