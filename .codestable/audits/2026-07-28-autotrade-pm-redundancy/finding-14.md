---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 14
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
summary: slot_balance 仅 from_cfg 赋值无人读取
tags: [autotrade-pm, dead-code]
---

# slot_balance 只在 from_cfg 赋值，全项目 autoTrade* 无人读取

## 位置

`tokenDemo/autoTrade_pm.py:473-475`

## 证据

```python
        # 初始化资金槽位(用于资金管理)(可覆盖)
        # 含义:用于控制单次下单的资金使用上限(与 open_ratio 一起作用)
        obj.slot_balance = kwargs.get("slot_balance", [0.0])
```

## 为什么是问题

`from_cfg` 仍把 `slot_balance` 从 kwargs 取出并挂到实例上，但全项目 `autoTrade_pm.py` / `autoTrade.py` / `autoTrade_papi.py` 对它只有注释与赋值，没有任何 `self.slot_balance` / `getattr` / `hasattr` 读取。开仓路径已改为 `RISK_PER_TRADE` / `MAX_POSITION_RATIO` 风险定仓，注释里“与 open_ratio 一起作用”也已过时。

唯一真实读写出现在 `dockerDemo/autoBN.py` 旧脚本的局部变量，与本类无继承或导入关系。因此该字段是遗留死属性：继续保留只会误导阅读者以为仍参与资金上限控制。

## 影响面

不修则实例上长期挂着无用字段，文档/注释继续暗示它与开仓资金上限有关，增加维护噪音；现网行为不受影响，因为本就无人读。

删除赋值与相关注释/文档键后：无任何执行路径行为变化（含异常、空数据、首次无缓存）；主入口 `from_cfg` 调用（`tokenDemo/autoTrade_pm.py:3597`）本就不传该参数；调用方若仍多传 kwargs，会被 `**kwargs` 静默忽略。测试侧 `test_autoTrade_pm.py`、`test_env_credentials.py` 等均不引用。同类文件 `autoTrade.py` / `autoTrade_papi.py` 同样只赋值不读，可一并清理；`tg2bn`、`stop_loss_example` 的 `open_ratio` 是另一套旧接口，与本字段无关。

## 建议改法

- 删除 `tokenDemo/autoTrade_pm.py:473-475` 的 `slot_balance` 赋值与相关注释；同步去掉 from_cfg 文档中的该键名（约 397 行注释）。
- 若仍要兼容外部调用方多传该 kwargs：显式忽略并打 debug 日志，但不要再挂实例属性。
- 同类遗留可顺带核对 `autoTrade.py` / `autoTrade_papi.py` 的同名字段赋值，但本条以 `autoTrade_pm.py` 为主。
- 不要写完整实现；此条仅发现、不定修，落地走 `cs-refactor`。

## 对抗验证记录

独立视角一：Read 确认 `autoTrade_pm.py:473-475` 为注释+赋值；全项目检索仅 pm/py/papi 三文件 from_cfg 注释键名与赋值，无任何 `self.slot_balance` 读取；开仓路径已用 `RISK_PER_TRADE`/`MAX_POSITION_RATIO`（约 788/795），与 slot 无关。独立视角二：交叉核对主入口不传参、测试不引用、`dockerDemo/autoBN.py` 为独立旧脚本局部变量；删除后无行为变化。结论：发现成立，非承重代码；定级 maintainability/P2、置信度 high 合理，未撞已定案项，也不只是 ruff ERA001 的注释标记。
