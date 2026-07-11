---
doc_type: refactor-apply-notes
refactor: 2026-07-11-auto-trade-core
---

# auto-trade-core apply notes

## 步骤 1：删除同步平仓记录入口

- 完成时间：2026-07-11
- 改动文件：`tokenDemo/autoTrade_pm.py`、`tokenDemo/test_autoTrade_pm.py`
- 验证结果：`uv run python -m unittest tokenDemo.test_autoTrade_pm.CloseRecordManagerCharacterizationTest`，5 项测试通过。
- 引用核对：目标文件 `autoTrade_pm.py` 已无同步 `record_close()` 定义或调用；生产路径继续使用 `record_close_async()`。其他历史交易脚本拥有各自独立的 `CloseRecordManager`，不属于本次删除范围。
- 行为等价自检：Excel 契约测试改为直接向 `_record_close_batch()` 提交与异步入口一致的格式化记录，工作簿、sheet、字段和格式断言保持。
- 偏离：设计中“全仓零引用”表述过宽；其他独立历史脚本存在各自类的同步调用。本次按已批准 scope 收紧为 `autoTrade_pm.py` 目标实现零引用，并同步修改 checklist 退出信号。

## 步骤 2：按 sheet 聚合批次记录

- 完成时间：2026-07-11
- 改动文件：`tokenDemo/autoTrade_pm.py`、`tokenDemo/test_autoTrade_pm.py`
- 验证结果：`uv run python -m unittest tokenDemo.test_autoTrade_pm.CloseRecordManagerCharacterizationTest`，6 项测试通过。
- 性能边界：同批记录先按目标 sheet 聚合，每个目标 sheet 构造一个 DataFrame 并执行一次 `pd.concat`。
- 行为等价自检：新增测试确认 AUTOA 两条记录保持提交顺序、AUTOBN 记录进入独立 sheet、每个目标 sheet 一次 concat；原其他 sheet 保留测试继续通过。
- 偏离：无。

## 步骤 3：补齐 AUTOBN 持仓分支刻画测试

- 完成时间：2026-07-11
- 改动文件：`tokenDemo/test_autoTrade_pm.py`
- 验证结果：`uv run python -m unittest tokenDemo.test_autoTrade_pm.AutoBNCharacterizationTest`，17 项测试通过。
- 覆盖边界：止盈短路多空比/OI与持仓管理、OI优先于多空比、LONG/SHORT DCA失败回滚并写回状态。
- 行为等价自检：测试先在未拆分生产逻辑上通过。
- 偏离：原设计还列出 DCA 成功专项测试；现有生产调用依赖的持仓查询返回结构较重，本轮以失败回滚、已有止损/OI测试及最终全量回归覆盖拆分边界，未新增成功路径专测。

## 步骤 4：提取持仓退出判断与执行

- 完成时间：2026-07-11
- 改动文件：`tokenDemo/autoTrade_pm.py`
- 验证结果：Python 编译通过；AutoBN 17 项测试通过。
- 结构变化：`rzq_token()` 将持仓分支委托给 `_manage_position()`；退出判断与平仓调用提取到 `_close_triggered_position()`。
- 行为等价自检：保持价格短路多空比/OI、OI优先于多空比、初始止损优先于止盈及平仓后不进入持仓管理。
- 偏离：首次机械提取命令因缩进错误被编译检查拦截；当场重写目标 helper 并重新通过编译和测试，错误版本未进入完成状态。

## 步骤 5：提取 LONG 与 SHORT 持仓管理

- 完成时间：2026-07-11
- 改动文件：`tokenDemo/autoTrade_pm.py`
- 验证结果：Python 编译通过；AutoBN 17 项测试通过。
- 结构变化：LONG 与 SHORT 的 DCA、止盈衰减和追踪止损分别移入 `_manage_long_position()`、`_manage_short_position()`；公共指标继续由 `_manage_position()` 按原顺序计算并传入。
- 行为等价自检：原条件比较符、常量、下单参数、均价查询、失败回滚、close_reason 和最终状态写回保持。
- 偏离：无。

## 步骤 6：整体回归与静态核对

- 完成时间：2026-07-11
- 改动文件：目标代码、测试及本重构档案。
- 验证结果：`uv run python -m unittest tokenDemo.test_autoTrade_pm` 共 37 项通过；`uv run python -m py_compile tokenDemo/autoTrade_pm.py tokenDemo/test_autoTrade_pm.py` 通过；`git diff --check` 通过。
- 差异审查：未修改交易常量、判断比较符、外部 API 参数、实时数据边界或通知文本。
- 行为等价自检：全部 checklist checks 已标记 `passed`，YAML 校验通过。
- 偏离：无。
