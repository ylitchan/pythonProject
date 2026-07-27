---
doc_type: issue-fix
issue: 2026-07-27-autoa-hist-fields-arg-mismatch
path: fast-track
status: completed
date: 2026-07-27
severity: P0
tags: [autoa, akshare, refactor-regression, signature]
---

# AUTOA日线历史调用点签名不匹配修复记录

## 1. 问题描述

AUTOA 运行日志中每只标的均报错跳过：

```
2026-07-27 10:39:00,078 - AUTOA - ERROR - 300534 处理失败，已跳过该标的:
TypeError: TypeError("AUTOA.stock_zh_a_hist() got multiple values for argument 'start_date'")
```

期望：AUTOA 正常拉取各标的日线历史并完成筛选。实际：所有依赖日线历史的路径全部抛 TypeError，标的被逐个跳过，策略等价于空跑。

## 2. 根因

重构提交 `9a1b5ee4`（♻️ 清理autoTrade_pm死代码）删除了 `AUTOA.stock_zh_a_hist` 的 `fields` 形参，但未同步更新调用点。函数体内 `fields` 确无使用，删形参方向正确，遗漏在调用方。

删除后签名为 `(cls, code, start_date=None, end_date=None, frequency="d", adjustflag="3")`，而 4 个调用点仍按位置传入 `"date,code,open,high,low,close,preclose,volume,amount"`，该字符串绑到第二个位置参 `start_date`，又与关键字 `start_date=` 冲突，故在**调用点绑定阶段**即抛 TypeError——函数自身的 `try/except` 无从捕获，日志走的是外层「处理失败，已跳过该标的」。

`autoTrade_papi.py:2489`、`autoTrade.py` 的同名方法仍保留 `fields` 形参，未受影响。

## 3. 修复方案

删除 4 个调用点的 `fields` 位置实参，其余参数与语义不动。

## 4. 改动文件清单

仅 `tokenDemo/autoTrade_pm.py`，4 处删除：

| 修复后行号 | 所在方法 | 场景 |
|---|---|---|
| 2796 | `_get_auction_price` | 集合竞价兜底取价 |
| 3091 | `on_positions` | 持仓/平仓观察 |
| 3308 | `filter_stocks` 开仓判断 | 量价切比雪夫 |
| 3453 | `_update_close_observation` | 收盘涨停池更新 |

## 5. 验证结果

- **调用点绑定校验**（AST 解析全部 `cls.stock_zh_a_hist(...)`，对真实运行时签名 `signature.bind`）：修复后 4/4 通过；对修复前版本反跑得 4/4 FAIL 且报错文本与线上日志一致，确认该校验非假绿。
- **离线端到端**（patch akshare 与新浪分时接口，跑真实函数体）：返回 5 根日线 + 1 根当日合成行，字段与数值符合预期；真实调用点 `_get_auction_price` 返回 12.40 正确。
- **全仓同类隐患扫描**（类作用域感知的 AST 绑定检查，覆盖 `autoTrade_pm.py` / `autoTrade_papi.py` / `autoTrade.py`）：356 个内部调用点，0 失败。
- `uv run ruff check tokenDemo/autoTrade_pm.py`：通过。
- `uv run python -m unittest`：88 项通过，`OK`。
- **真实网络端到端未执行**：当前环境出网被拦截（akshare 报 `RemoteDisconnected`），线上行情验证需在可联网环境复跑。

## 6. 遗留事项

- **测试覆盖盲区（本 bug 的真正放行原因）**：`test_autoTrade_pm.py` 中 `stock_zh_a_hist` 一律被 `AsyncMock()` 整体替换（145/186/251/283/320/436/454/1984 行），mock 接受任意实参，签名不匹配无法暴露——所以 `9a1b5ee4` 当时「53 个单测通过」是假绿。建议给该类 mock 加 `autospec=True`，或把上述绑定校验固化成一个常驻测试。属独立改进，未在本次修复内实施。
- 真实行情端到端验证待联网环境补做。
