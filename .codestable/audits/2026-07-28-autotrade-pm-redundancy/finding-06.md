---
doc_type: audit-finding
audit: 2026-07-28-autotrade-pm-redundancy
finding: 06
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
summary: 多空开仓观察信号块结构近乎复制未抽取
tags: [autotrade-pm, dup-code]
---

# 多空开仓观察信号块结构近乎复制未抽取

## 位置

`tokenDemo/autoTrade_pm.py:1985-2013,2027-2055`

## 证据

```python
if long_ok:
    # 在基差率判断前发送观察信号
    hl2 = (kline[-1][2] + kline[-1][3]) / 2
    atr_value = self.calculate_atr(kline)
    zy_msg, zs_msg = self.calc_stop_profit_loss(
        hl2,
        is_long=True,
        atr=atr_value,
    )
    if not (zy_msg == 0 and zs_msg == 0):
        basis_rate = await self.get_basis_rate(symbol)
        if basis_rate < -self.BASIS_RATE_THRESHOLD:
            open_info.strategy.append(PositionSide.Basis)
        lsr_show = (
            f"{long_lsr:.4f}" if long_lsr is not None else "N/A"
        )
        rate_show = (
            atr_value * self.SUPERTREND_FACTOR / current_price
        )
        strategy_tag = format_strategy_tags(open_info.strategy)
        await self.send_msg(
            f"==={symbol}**{strategy_tag}**===\n价格:{current_price}\n基差率:{basis_rate:.4%}\n多空比:{lsr_show}\n止盈:{zy_msg}\n止损:{zs_msg}\n收益率:{rate_show:.2%}",
            qy_key=self.signal_qy_key,
        )
        await self.send_msg(
            f"==={symbol}**{strategy_tag}**===\n价格:{current_price}\n基差率:{basis_rate:.4%}\n多空比:{lsr_show}\n止盈:{zy_msg}\n止损:{zs_msg}\n收益率:{rate_show:.2%}"
        )
        open_info.side = OrderSide.BUY
        should_open = True
# short_ok 分支同构：hl2/atr/calc_stop/basis/lsr_show/rate_show/双 send_msg/side/should_open，
# 仅 is_long、基差方向、lsr 来源、BUY/SELL 不同（2027-2055）
```

## 为什么是问题

`long_ok`（1985-2013）与 `short_ok`（2027-2055）两段约 29 行流程同构：算 hl2 → ATR → `calc_stop_profit_loss` → 非零守卫 → 拉基差 → 可选挂 Basis → 格式化多空比/收益率/策略标签 → 双通道 `send_msg` → 写 side → `should_open=True`。

差异仅 `is_long`、基差阈值比较方向（`< -THRESHOLD` vs `> +THRESHOLD`）、lsr 变量（`long_lsr`/`short_lsr`）与 `OrderSide`（BUY/SELL）。散落两处导致改通知文案或开仓前置条件必须改两次，属于典型未封装重复。

## 影响面

不修则通知文案、基差阈值门槛、止盈止损前置守卫任一变更都要同步改两处，易漏改一侧造成多空行为分叉。

涉及点：

- 多头观察信号块：`tokenDemo/autoTrade_pm.py:1985-2013`
- 空头观察信号块：`tokenDemo/autoTrade_pm.py:2027-2055`
- 下游开仓复用 hl2/atr/zy/zs：`tokenDemo/autoTrade_pm.py:2061-2069`
- 回归覆盖：`tokenDemo/test_autoTrade_pm.py` 约 1230-1346（mock `check_side`/`calc_stop`/`get_basis_rate`/`send_msg`/`open_bn_position`）

`check_side` 调用处的 `stop_guard_threshold` 不对称（1974-1983 / 2020-2026）在重复块之外，不阻碍信号块抽取。

## 建议改法

抽成内部方法，参数化 `is_long`、`lsr`、基差阈值条件与 side；返回 `(should_open, hl2, atr, zy, zs, basis_rate)` 供后续开仓复用，避免与 2061-2069 死路径问题叠加。

要点：

- `is_long` 传入 `calc_stop_profit_loss`，并由其推导 `OrderSide`
- 基差方向可写成 `basis_rate * (-1 if is_long else 1) > THRESHOLD`，或传入比较谓词
- `lsr` 由调用方传入
- 抽取后 long/short 调用点各一行，行为保持不变

不要在 cs-audit 阶段写完整实现。

## 对抗验证记录

两个独立视角核验后结论一致、不予推翻：视角一确认 long_ok(1985-2013) 与 short_ok(2027-2055) 均为 hl2→ATR→calc_stop→非零守卫→基差→格式化→双 send_msg→写 side→should_open 的约 29 行同构流程；视角二确认差异均可参数化（is_long/基差方向/lsr/side），各执行路径行为不变，既有测试可回归，定级 maintainability/P2/high 合理。
