---
doc_type: audit-finding
id: F-01
nature: performance
severity: P1
confidence: high
suggested_action: cs-refactor
source: tokenDemo/autoTrade_pm.py
---

# F-01 每次平仓记录都会全量读写 Excel 所有 sheet

## 证据

`CloseRecordManager.record_close()` 在每次平仓时都会读取整个 Excel 文件的所有 sheet：

```python
with pd.ExcelFile(cls._excel_file, engine="openpyxl") as xls:
    for name in xls.sheet_names:
        existing_sheets[name] = pd.read_excel(
            xls, sheet_name=name
        )
```

位置：`tokenDemo/autoTrade_pm.py:234`

随后又把所有 sheet 全量写回：

```python
with pd.ExcelWriter(cls._excel_file, engine="openpyxl") as writer:
    for name, data in existing_sheets.items():
        data.to_excel(writer, sheet_name=name, index=False)
```

位置：`tokenDemo/autoTrade_pm.py:254`

该函数被 AUTOBN 平仓路径调用：`tokenDemo/autoTrade_pm.py:957`，也被 AUTOA 平仓路径调用：`tokenDemo/autoTrade_pm.py:3058`。

## 为什么是问题

平仓记录是追加型数据，但当前实现是“每追加 1 行，读全 workbook + 写全 workbook”。随着 `close_records.xlsx` 增大，单次平仓 I/O 会线性变慢；如果多个标的同一轮触发平仓，虽然有锁避免并发写坏文件，但会串行执行多次全量读写，容易拖慢监控任务。

## 影响

- 平仓通知和记录写入变慢。
- Excel 文件增长后，`record_close_async()` 可能触发 `IO_TIMEOUT_SECONDS = 15` 超时。
- 平仓路径中等待记录写入，可能影响后续标的处理。

## 建议

走 `cs-refactor`：

1. 将平仓记录主存储改为追加友好的 CSV/JSONL/SQLite。
2. Excel 作为导出产物，定时或手动生成，而不是每笔平仓实时全量重写。
3. 如果必须保留 Excel 实时写入，至少只读取/更新目标 sheet，并考虑批量缓冲写入。