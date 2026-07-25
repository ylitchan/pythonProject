---
doc_type: refactor-apply-notes
refactor: 2026-07-25-auto-trade-dead-code
---

# auto-trade-dead-code apply notes

## 步骤 1：删除无用导入和无效局部赋值

- 完成时间：2026-07-25
- 改动文件：`tokenDemo/autoTrade_pm.py`
- 验证结果：删除 `copy`、重复 HTTP session 获取和未读取的 `is_long`；Ruff F401/F841 检查通过。
- 偏离：无。

## 步骤 2：删除零引用私有包装方法

- 完成时间：2026-07-25
- 改动文件：`tokenDemo/autoTrade_pm.py`
- 验证结果：删除 `_new_order_via_papi`、`_change_leverage_via_papi`、`_call_um`；目标文件内搜索为 0。
- 偏离：旧版 `autoTrade.py` / `autoTrade_papi.py` 有独立同名实现，按本次锁定范围未修改。

## 步骤 3：收窄未使用参数

- 完成时间：2026-07-25
- 改动文件：`tokenDemo/autoTrade_pm.py`
- 验证结果：删除 `stock_zh_a_hist.fields`；`frame` 改为 `_frame` 且保留信号回调双参数协议；Vulture 80%+ 扫描无输出。
- 偏离：无。

## 步骤 4：机械收口与全量验证

- 完成时间：2026-07-25
- 改动文件：`tokenDemo/autoTrade_pm.py`
- 验证结果：`git diff --check` 通过；Ruff F401/F841/F811/F821/F822/F823 通过；53 个 `tokenDemo.test_autoTrade_pm` 测试通过；AUTOA parity 的 ATR、切比雪夫、BZ、阳线/跳空、持仓 ATR、N 条件全部零差异。
- 偏离：无。
