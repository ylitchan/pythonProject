---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 12
nature: performance
severity: P2
confidence: high
suggested_action: cs-refactor
summary: calculate_atr 提取数组后仍用 iloc 重取高低价
tags: [autotrade-pm, repeat-call]
---

# calculate_atr 已提取 numpy 数组后又用 iloc 重取最新高低价

## 位置

`tokenDemo/autoTrade_pm.py:2499-2515`

## 证据

```python
highs = hist_data["high"].values
lows = hist_data["low"].values
closes = hist_data["close"].values

for i in range(1, len(hist_data)):
    h = float(highs[i])
    low_price = float(lows[i])
    pc = float(closes[i - 1])

    tr = max(h - low_price, abs(h - pc), abs(low_price - pc))
    tr_list.append(tr)

if not tr_list:
    return 0.0
atr = sum(tr_list[-period:]) / min(len(tr_list), period)
latest_high = float(hist_data.iloc[-1]["high"])
latest_low = float(hist_data.iloc[-1]["low"])
```

## 为什么是问题

同一执行路径里已经把 `high`/`low` 抽成 numpy 数组 `highs`/`lows`，TR 循环末轮（`i=len-1`）实际上已经读过 `highs[-1]`/`lows[-1]`；末尾却再走两次 DataFrame `iloc` 标签索引取同一行的 high/low，做 hl2/atr_cap 计算。属于同路径内对同一份已物化数据的二次按位读取。

应直接用 `float(highs[-1])` / `float(lows[-1])`，避免在已提取 `.values` 后仍回退到 DataFrame 索引访问。

## 影响面

不修则每次 `AUTOA.calculate_atr` 正常路径都会多两次 `iloc` 标签取数，属微冗余，路径必然触发。

主要调用点：

- 持仓路径：`tokenDemo/autoTrade_pm.py:3076`（`on_positions`）
- 开仓路径：`tokenDemo/autoTrade_pm.py:3288`
- 对拍测试：`tokenDemo/test_backtest_autoa_parity.py` 传入标准 OHLCV DataFrame

上述调用点均不依赖 iloc 标签语义；修后返回值在标准 hist 路径上应保持等价。

## 建议改法

将 `latest_high`/`latest_low` 改为从已提取数组取末元素，去掉对 `hist_data.iloc[-1]` 的二次访问：

- `latest_high = float(highs[-1])`
- `latest_low = float(lows[-1])`

注意：空/过短数据在 2494-2495 早退，到不了此处；病态列名重复 DF 会在循环里 `float(highs[i])` 先炸，与 iloc 路径无行为分叉。不要在 cs-audit 阶段写完整实现。

## 对抗验证记录

两个独立视角核验后结论一致、不能推翻：视角一确认 2499-2515 先 `.values` 物化再 iloc 重取，属同路径重复取数；视角二确认 `highs[-1]`/`lows[-1]` 与 `iloc` 末行 high/low 在标准 OHLCV（含切片未 reset、reset_index、dropna 后追加今日行等）语义等价，调用点均传标准 DF，非网络/缓存问题，P2/high 定级合理。
