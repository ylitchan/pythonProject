---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 03
nature: maintainability
severity: P1
confidence: high
suggested_action: cs-refactor
summary: from_cfg 写入 margin_mode 后全文件从未使用
tags: [autotrade-pm, dead-code]
---

# from_cfg 解析并写入 margin_mode，全文件无任何读取或下单使用

## 位置

`tokenDemo/autoTrade_pm.py:407-426`

## 证据

```python
        # 仓位模式：'CROSSED' 全仓，'ISOLATED' 逐仓；支持大小写/中文/别名
        # 仅设置新开仓/下单前的目标模式；若该 symbol 已有仓位，交易所可能拒绝切换
        margin_mode_raw = (
            str(kwargs.get("margin_mode", kwargs.get("position_mode", "CROSSED")))
            .strip()
            .lower()
        )
        margin_mode_map = {
            "cross": "CROSSED",
            "crossed": "CROSSED",
            "全仓": "CROSSED",
            "全倉": "CROSSED",
            "c": "CROSSED",
            "isolated": "ISOLATED",
            "iso": "ISOLATED",
            "逐仓": "ISOLATED",
            "逐倉": "ISOLATED",
            "i": "ISOLATED",
        }
        obj.margin_mode = margin_mode_map.get(margin_mode_raw, "CROSSED")
```

## 为什么是问题

`from_cfg` 从 kwargs 解析 `margin_mode` / `position_mode` 并写入 `obj.margin_mode`，但全项目中该属性从未被读取：`open_bn_position`、`close_bn_position`、`_call_api` 均不读 `self.margin_mode`，也不调用 change margin type 类 API。`git log -S "self.margin_mode"` 在 autoTrade / autoTrade_pm / autoTrade_papi 三文件上均无命中，说明历史上也从未被消费。

对统一账户（PAPI）路径而言，这整块是配置残骸。调用方传入 `margin_mode` / `position_mode` 会被静默吞掉并只存进属性，却不会真正切换仓位模式，产生“已切换仓位模式”的假象。注释自称“仅设置新开仓/下单前的目标模式”，但下单前从未调用对应切换 API，属于未完成能力留下的死代码，而非承重逻辑。

## 影响面

不修的话：调用方（例如 `tgDemo/tg2bn.py:44` 传 `margin_mode="CROSSED"`）会继续被静默吞掉，配置看起来生效实则无效；`autoTrade.py` / `autoTrade_papi.py` 的对称 `from_cfg` 同样保留无用解析，增加维护噪音。

修了（删除解析与赋值）后：开仓/平仓/异常/空数据/无缓存路径均不变——属性本就不参与任何控制流。调用方传参仍会被 `**kwargs` 静默忽略，与现状“静默存储后不生效”行为一致。测试 `test_autoTrade_pm.py` / `test_env_credentials.py` 不断言、不依赖该字段。相关写入点：

- `tokenDemo/autoTrade_pm.py:407-426`（本 finding 主目标）
- `tokenDemo/autoTrade.py`、`tokenDemo/autoTrade_papi.py` 对称 `from_cfg` 赋值
- 外部传入参考：`tgDemo/tg2bn.py:44`

## 建议改法

若 PAPI 不再支持或不需要切换保证金模式：

1. 删除 `from_cfg` 中 `margin_mode` 解析、`margin_mode_map` 与 `obj.margin_mode` 赋值。
2. 同步更新注释中的支持键列表（去掉 `margin_mode` / `position_mode`）。
3. 对 `autoTrade.py` / `autoTrade_papi.py` 的对称 `from_cfg` 做同样清理，避免三文件继续分叉。

若仍需真正支持切换：应在开仓前调用对应 change margin type API，并处理“该 symbol 已有仓位时交易所可能拒绝切换”的失败路径；仅写属性不算完成能力。

## 对抗验证记录

视角一：全项目 Grep `self.margin_mode` / `obj.margin_mode` / `.margin_mode` 仅命中三处 from_cfg 赋值，无任何读取；`open_bn_position`（`autoTrade_pm.py:723+`）只使用 leverage 与 `change_um_initial_leverage` / `new_um_order`，无 change margin type。视角二：独立复核确认 `tokenDemo/autoTrade_pm.py:407-426` 与证据一字不差，`tgDemo/tg2bn.py:44` 传入恰印证静默吞参；删除赋值后控制流不变。结论：发现成立，不能推翻；maintainability / P1 / high 定级合理，行号无需订正。
