# autoTrade_pm.py 开仓条件梳理

本文只梳理 `tokenDemo/autoTrade_pm.py` 中 **AUTOA** 与 **AUTOBN** 的开仓条件、观察条件、确认条件、风控约束与触发顺序，尽量按实际代码路径展开。

---

## 一、整体结构

文件里的开仓不是“发现信号立刻下单”的单层结构，而是统一走两段式：

1. **先进入观察列表 `OBSERVATIONS`**
2. **后续再次满足确认条件时，才真正开仓 / 建仓**

两套系统都遵循这个思路：

- **AUTOBN**：先从日线和成交量生成观察信号，再结合多空比、OI、基差率、ATR、冷却时间决定是否实际开仓。见 `tokenDemo/autoTrade_pm.py:2020`、`tokenDemo/autoTrade_pm.py:1868`。
- **AUTOA**：先在收盘后把涨停池股票加入观察列表，之后盘中逐分钟检查是否满足低吸/放量突破条件，满足后转为持仓。见 `tokenDemo/autoTrade_pm.py:3071`、`tokenDemo/autoTrade_pm.py:2951`。

---

## 二、AUTOBN 开仓条件

## 2.1 AUTOBN 的运行入口

AUTOBN 的主入口是 `rzq_market()` / `_rzq_market_impl()`，每分钟调度一次，并按 5 分钟窗口分片处理交易对。见：

- `tokenDemo/autoTrade_pm.py:2151`
- `tokenDemo/autoTrade_pm.py:2185`
- `tokenDemo/autoTrade_pm.py:3367`

每次处理单个 symbol 的核心函数是：

- `rzq_token()`：`tokenDemo/autoTrade_pm.py:1485`

这个函数里，和开仓有关的流程顺序是：

1. 读取当前 symbol 是否已经有持仓 `POSITIONS`
2. 读取是否已经在观察列表 `OBSERVATIONS`
3. 如果有观察记录，尝试确认并开仓
4. 不论是否已在观察阶段，再判断今天是否要新建观察记录

这意味着 AUTOBN 是一个“**观察 → 确认 → 开仓 → 持仓管理**”的循环系统。

---

## 2.2 AUTOBN 新建观察记录的条件

代码位置：`tokenDemo/autoTrade_pm.py:2020`

只有当 `can_set_observation == True` 时，才会为 symbol 新建观察信号。

### 2.2.1 同一 UTC 日期只记录一次观察

如果该 symbol 已有 `open_info`，会取：

- 观察记录的 UTC 日期
- 当前时间的 UTC 日期

只有二者不同，才允许再次写入新的 observation。见 `tokenDemo/autoTrade_pm.py:2021-2029`。

也就是说：

- **同一 UTC 日内不会重复发同类观察信号**
- 下一 UTC 日才允许重新生成新的观察记录

### 2.2.2 做多观察信号（BZ）

代码：`tokenDemo/autoTrade_pm.py:2034-2045`

满足以下条件时，生成：

- `kline_close[-2] < current_price`
- `kline_volume[-1] >= max(kline_volume[-self.VOLUME_LOOKBACK_PERIOD:])`

其中：

- `current_price = kline_close[-1]`
- `VOLUME_LOOKBACK_PERIOD = 10`，见 `tokenDemo/autoTrade_pm.py:307`

可以理解为：

1. **当前收盘价高于前一日收盘价**
2. **当前成交量达到最近 10 根日 K 的最大值**

满足后，写入观察记录：

- `side = BUY`
- `strategy = [BZ]`

即它只是先标记为一个潜在做多观察对象，不会立刻开仓。

### 2.2.3 做空观察信号（BD）

代码：`tokenDemo/autoTrade_pm.py:2046-2056`

满足以下条件时，生成：

- `max(kline_close[-3:]) >= max(kline_close)`
- `max(kline_volume[-3:]) >= max(kline_volume)`

可理解为：

1. **最近 3 根 K 线里出现了全样本最高收盘价**
2. **最近 3 根 K 线里出现了全样本最高成交量**

随后写入：

- `side = SELL`
- `strategy = [BD]`

注意这里不是“当前这根”必须创新高，而是“最近 3 根里”存在价量极值，因此它更像一个顶部/拐点观察信号。

---

## 2.3 AUTOBN 从观察到真正开仓的总前提

代码：`tokenDemo/autoTrade_pm.py:1868-2018`

当 symbol 已经在 `OBSERVATIONS` 中时，会进入确认逻辑。

在真正开仓前，先有两个大前提：

### 2.3.1 观察记录不能过期

代码：`tokenDemo/autoTrade_pm.py:1869-1875`

- `OBSERVATION_TIMEOUT_SECONDS = 24 * 60 * 60`
- 即 **观察记录保留 1 天**

如果超时：

- 直接从 `OBSERVATIONS` 删除
- 本轮不再参与开仓判断

### 2.3.2 必须已经有观察策略标签

后续确认分两支：

- `PositionSide.BZ in open_info.strategy` 才走做多确认
- `PositionSide.BD in open_info.strategy` 才走做空确认

因此，AUTOBN 的实际开仓一定是由先前的观察信号驱动的，不会凭空开仓。

---

## 2.4 AUTOBN 做多开仓确认条件

做多确认代码主要在：

- `tokenDemo/autoTrade_pm.py:1880-1923`
- `tokenDemo/autoTrade_pm.py:1005-1185`（`check_side(..., LONG)`）

### 2.4.1 第一层：价格方向必须继续向上

先决条件：

- `PositionSide.BZ in open_info.strategy`
- `kline_close[-2] < current_price`

也就是：

- 观察记录里有做多标签 BZ
- 当前收盘仍高于前一日收盘

如果价格没有继续向上，连 `check_side()` 都不会调用。

### 2.4.2 第二层：多空比基础过滤

在 `check_side(symbol, LONG, ...)` 中：

- 先取多空人数比 `long_short_ratio_data`，见 `tokenDemo/autoTrade_pm.py:1068`
- 当前值 `lsrd = lsr_values[-1]`

必须先满足：

- `lsrd < OPEN_LONG_SHORT_RATIO_THRESHOLD`
- 其中 `OPEN_LONG_SHORT_RATIO_THRESHOLD = 6 / 4 = 1.5`，见 `tokenDemo/autoTrade_pm.py:344`

即：

- **当前多空比不能过热**
- 如果当前多空比 `>= 1.5`，直接拒绝做多开仓

### 2.4.3 第三层：多空比极值 / 阈值二选一

继续要求以下两者之一成立：

1. **极值条件**：
   - `lsrd <= min(recent_lsr_values)`
   - 其中 `recent_lsr_values = lsr_values[-LONG_SHORT_RATIO_EXTREME_LOOKBACK:-1]`
   - `LONG_SHORT_RATIO_EXTREME_LOOKBACK = 10`
2. **阈值条件**：
   - `lsrd < LONG_SHORT_RATIO_LONG_LIMIT`
   - `LONG_SHORT_RATIO_LONG_LIMIT = 3 / 7 ≈ 0.4286`

也就是做多时要求当前多空比处于非常有利的区间：

- 要么比最近窗口更低，属于极端低位
- 要么直接低于固定阈值 3/7

代码见：`tokenDemo/autoTrade_pm.py:1095-1107`

### 2.4.4 第四层：1h OI 与 5m OI 的融合结构必须支持做多

这部分是 AUTOBN 做多开仓里最细的一层过滤。代码见：

- `tokenDemo/autoTrade_pm.py:1109-1171`

关键过程：

1. 读取当前整点对齐的 `1h OI` 历史
2. 读取最新 `5m OI`
3. 提取：
   - `latest_oi_1h`
   - `oi_5m_last`
   - 5m 最新 long ratio
   - 对齐到整点或不晚于整点的 1h ratio
4. 计算融合值：

```python
blend = (
    latest_oi_1h * long_ratio_1h
    + (oi_5m_last - latest_oi_1h) * self.OI_DELTA_LONG_RATIO_WEIGHT
) / current_total_oi
```

其中：

- `OI_DELTA_LONG_RATIO_WEIGHT = 0.55`

然后要求：

- `blend > long_ratio_5m`

如果 `blend <= long_ratio_5m`，直接拒绝做多。

直观上，这一步是在判断：

- 当前 OI 变化结构是否真的支持“更强的多头质量”
- 而不是只看表面上的 5m 多空比

### 2.4.5 第五层：OI 必须处于历史极端高位

这里有一个关键样本切片：

- `oi_hist_for_cheb = sumOpenInterest_1h[:-self.OI_CHEB_EXCLUDE_RECENT_COUNT]`
- `OI_CHEB_EXCLUDE_RECENT_COUNT = 10`
- `OI_QUERY_LIMIT = 30`

也就是：

- `sumOpenInterest_1h` 最多取最近 `30` 条 1h OI 数据
- 其中 **最近 10 条会被排除**，不参与切比雪夫样本统计
- 真正用于统计极值判断的是 **更早的前 20 条 1h OI 历史样本**

写成索引范围就是：

- 原始样本：`sumOpenInterest_1h[0:30]`（最多 30 条）
- 统计样本：`sumOpenInterest_1h[0:20]`
- 被排除的近期样本：`sumOpenInterest_1h[20:30]`

如果实际返回不足 30 条，则含义不变：

- 永远是“**去掉最近 10 条，只拿更早的部分做极值统计**”

继续要求：

- `oi_5m_last >= max(sumOpenInterest_1h)`

即：

- **当前 5m OI 至少不低于整组 1h 样本中的最大值**

同时再要求切比雪夫极端概率满足：

- `calculate_chebyshev_probability(oi_hist_for_cheb, oi_5m_last)["chebyshev_upper_bound"] < CHEBYSHEV_EXTREME_THRESHOLD`
- `CHEBYSHEV_EXTREME_THRESHOLD = 0.01`

这表示：

- 当前 OI 不是普通偏高，而是相对“更早历史基线”形成的统计意义上的极端异常高位
- 代码刻意排除了最近 10 条 1h OI，避免近期已经抬高的 OI 水平把极值判断稀释掉

代码见：`tokenDemo/autoTrade_pm.py:1172-1184`

### 2.4.6 做多确认成功后的附带数据

若通过，会返回：

- `True`
- 当前多空比 `lsrd`
- `oi_guard_threshold = max(oi_hist_for_cheb)`

这里的 `oi_guard_threshold` 会在后续建仓后写入 `Position.oi_guard_threshold`，供后续 DCA 风控使用。见：

- `tokenDemo/autoTrade_pm.py:1180-1184`
- `tokenDemo/autoTrade_pm.py:2008-2012`

---

## 2.5 AUTOBN 做空开仓确认条件

代码位置：

- `tokenDemo/autoTrade_pm.py:1924-1964`
- `tokenDemo/autoTrade_pm.py:1017-1067`（`check_side(..., SHORT)`）

### 2.5.1 第一层：价格方向必须转弱

要求：

- `not long_ok`
- `PositionSide.BD in open_info.strategy`
- `current_price < kline_close[-2]`

即：

1. 做多确认没有通过
2. 观察记录里有做空标签 BD
3. 当前价格低于前一日收盘

### 2.5.2 第二层：当前 5m OI 必须处于极低位

在 SHORT 分支中，先拉取 `oi_5m`，得到：

- `oi_5m_last = float(oi_5m[-1]["sumOpenInterest"])`

然后获取按当天 8 点对齐的 `1d OI` 历史数据。见：

- `tokenDemo/autoTrade_pm.py:1024-1048`

要求：

- `oi_5m_last <= min(sumOpenInterest_1d)`

即：

- **当前 5m OI 不高于 1d 历史样本最小值**

### 2.5.3 第三层：低 OI 必须是统计意义上的极端事件

这里的样本切片和 LONG 不一样，SHORT 分支写法是：

- `oi_hist_for_cheb = sumOpenInterest_1d[-(self.OI_QUERY_LIMIT - self.OI_CHEB_EXCLUDE_RECENT_COUNT):]`
- `OI_QUERY_LIMIT = 30`
- `OI_CHEB_EXCLUDE_RECENT_COUNT = 10`

按当前代码直译，它取的是：

- `sumOpenInterest_1d[-20:]`
- 也就是 **最近 20 条 1d OI 数据**

注意这里和 LONG 分支不同：

- LONG：是 `[:-10]`，明确排除了最近 10 条
- SHORT：是 `[-20:]`，实际上保留的是尾部最近 20 条，并没有再额外剔除最近 10 条

所以 SHORT 当前真实采用的切比雪夫样本范围是：

- **最近 20 条 1d OI 历史**

然后要求：

- `calculate_chebyshev_probability(oi_hist_for_cheb, oi_5m_last)["chebyshev_upper_bound"] < SHORT_OI_CHEB_THRESHOLD`
- `SHORT_OI_CHEB_THRESHOLD = 0.05`

即：

- 当前低 OI 必须是相对最近 20 条 1d OI 历史的异常低位，而不是普通回落

代码见：`tokenDemo/autoTrade_pm.py:1058-1065`

### 2.5.4 做空确认通过后的返回值

SHORT 分支通过后返回：

- `(True, None, None)`

说明做空开仓不会像做多那样把 `long_short_ratio` 和 `oi_guard_threshold` 带进持仓。

---

## 2.6 AUTOBN 基差率标签条件

无论做多还是做空，只要已经通过方向确认，在真正下单前还会读取基差率 `basis_rate`。见：

- 做多：`tokenDemo/autoTrade_pm.py:1906-1908`
- 做空：`tokenDemo/autoTrade_pm.py:1947-1949`

### 2.6.1 做多时

若：

- `basis_rate < -BASIS_RATE_THRESHOLD`
- `BASIS_RATE_THRESHOLD = 0.02`

则向 `open_info.strategy` 追加：

- `PositionSide.Basis`

即：

- **期货相对指数出现超过 2% 的贴水时，给做多信号增加 Basis 标签**

### 2.6.2 做空时

若：

- `basis_rate > BASIS_RATE_THRESHOLD`

则追加：

- `PositionSide.Basis`

即：

- **期货相对指数出现超过 2% 的升水时，给做空信号增加 Basis 标签**

注意：

- 基差率不会阻止开仓
- 它只是附加标签，不是硬门槛

---

## 2.7 AUTOBN 真正下单前的统一开仓前置约束

当 `should_open == True` 后，进入真正下单阶段。代码：`tokenDemo/autoTrade_pm.py:1965-1996`

### 2.7.1 24 小时内平仓过的标的不允许重开

要求：

- `current_timestamp - last_close_ts >= REOPEN_COOLDOWN_SECONDS`
- `REOPEN_COOLDOWN_SECONDS = 24 * 60 * 60`

也就是：

- **同一 symbol 平仓后 24 小时内不允许再次开仓**

代码：`tokenDemo/autoTrade_pm.py:1966-1974`

### 2.7.2 必须能算出 ATR 止盈止损

通过：

- `hl2 = (high + low) / 2`
- `atr_value = calculate_atr(kline)`
- `zy, zs = calc_stop_profit_loss(hl2, is_long=is_long, atr=atr_value)`

如果：

- `zy == 0 and zs == 0`

则直接返回，不开仓。见 `tokenDemo/autoTrade_pm.py:1976-1984`

也就是说：

- **ATR 是 AUTOBN 真正开仓不可缺少的条件**
- 没有有效 ATR，就不会下单

---

## 2.8 AUTOBN `open_bn_position()` 内部的硬性下单条件

真正的下单函数：`tokenDemo/autoTrade_pm.py:719`

即使前面的方向确认都通过了，这里仍可能因为账户或风控约束导致不开仓。

### 2.8.1 账户可用余额必须大于 0

- `balance = availableBalance`
- `if balance <= 0: return None`

见：`tokenDemo/autoTrade_pm.py:754-757`

### 2.8.2 必须能拿到标记价格

- `mark_price_data` 不能为空
- 否则不开仓

见：`tokenDemo/autoTrade_pm.py:759-761`

### 2.8.3 symbol 必须在 `symbols_info` 中

否则说明没有交易对元数据，不能计算精度，也就不能下单。见：`tokenDemo/autoTrade_pm.py:765-767`

### 2.8.4 止损价与止盈价都必须有效

要求：

- `stop_loss_price is not None and stop_loss_price > 0`
- `take_profit_price is not None and take_profit_price > 0`
- `stop_loss_gap > 0`
- `take_profit_gap > 0`

见：`tokenDemo/autoTrade_pm.py:769-781`

### 2.8.5 仓位大小不是固定值，而是风控定仓

核心过程：

1. `risk_amount = total_balance * RISK_PER_TRADE`
2. `target_profit = total_balance * TARGET_PROFIT_RATIO`
3. `amount_by_sl = risk_amount / stop_loss_gap`
4. `amount_by_tp = target_profit / take_profit_gap`
5. `amount_raw = (amount_by_sl + amount_by_tp) / 2`

对应常量：

- `RISK_PER_TRADE = 0.1`
- `TARGET_PROFIT_RATIO = 0.1`

见：`tokenDemo/autoTrade_pm.py:783-790`

这意味着：

- 仓位由“止损距离”和“止盈距离”共同决定
- 不是简单满仓或固定手数

### 2.8.6 单币种名义仓位有上限

- `max_notional = balance * MAX_POSITION_RATIO`
- `MAX_POSITION_RATIO = 0.1`

如果按风险算出的 `amount_raw` 对应名义价值过大，会被压缩到上限。见：`tokenDemo/autoTrade_pm.py:791-798`

即：

- **单个币种的名义仓位最多只用可用余额的 10%**

### 2.8.7 下单后名义价值必须达到最小门槛

要求：

- `notional >= MIN_NOTIONAL`
- `MIN_NOTIONAL = 10`

否则不开仓。见：`tokenDemo/autoTrade_pm.py:806-810`

### 2.8.8 保证金必须足够

要求：

- `required_margin = notional / leverage`
- `required_margin <= balance`

否则不开仓。见：`tokenDemo/autoTrade_pm.py:811-814`

### 2.8.9 账户健康度必须达标

调用：

- `account_health = await self.calculate_health_bn(notional, account_data)`

要求：

- `account_health >= health4open`
- 默认 `DEFAULT_HEALTH_THRESHOLD = 70`

见：`tokenDemo/autoTrade_pm.py:815-817`

### 2.8.10 通过后才会设置杠杆并市价单开仓

- 先 `change_um_initial_leverage`
- 再 `new_um_order(... MARKET ...)`

见：`tokenDemo/autoTrade_pm.py:819-835`

因此，AUTOBN 的“真正开仓”必须同时满足：

- 方向确认通过
- 冷却期通过
- ATR 可计算
- 账户余额与健康度通过
- 风险仓位、最小名义价值、保证金都通过

---

## 三、AUTOA 开仓条件

## 3.1 AUTOA 的整体链路

AUTOA 的思路和 AUTOBN 一样，也是两段式，但来源不同：

1. **收盘后从涨停池选股，加入观察列表**
2. **下一交易日盘中监控，满足放量突破 / 特定形态后，转为持仓**

核心函数：

- `filter_stocks()`：`tokenDemo/autoTrade_pm.py:3071`
- `on_observations()`：`tokenDemo/autoTrade_pm.py:2951`
- `monitor_stocks()`：`tokenDemo/autoTrade_pm.py:3221`

AUTOA 没有真正下单到券商接口，而是：

- 满足条件后把股票写入 `alert_all["POSITIONS"]`
- 发送开仓通知

也就是说它更像一套 **A 股信号建仓/持仓跟踪系统**。

---

## 3.2 AUTOA 进入观察列表的条件

### 3.2.1 仅在交易时段 / 交易日内运行

`filter_stocks()` 先检查：

- 9:30 前不执行
- 15:05 后不执行
- 若今天不在交易日列表 `zt_dates` 中，不执行

见：`tokenDemo/autoTrade_pm.py:3081-3096`

### 3.2.2 若没有交易日缓存，会先取最近交易日列表

调用：

- `get_last_trading_days(today)`，见 `tokenDemo/autoTrade_pm.py:2600`

它会从新浪财经获取交易日历，并返回最近若干交易日列表，用于后续取历史 K 线和涨停池。

### 3.2.3 观察列表是在收盘时由涨停池补充的

关键条件：

- `if today.hour == cls.MARKET_CLOSE_HOUR:`
- `MARKET_CLOSE_HOUR = 15`

在这一分支中，会调用：

- `ak.stock_zt_pool_em(date=cls.zt_dates[0].replace("-", ""))`

获取当天涨停池。见：`tokenDemo/autoTrade_pm.py:3102-3115`

### 3.2.4 涨停池个股加入观察列表的逻辑

对每只涨停池股票：

1. 获取历史数据 `stock_zh_a_hist(...)`
2. 若历史为空则跳过
3. 取当日收盘价 `price_close`

然后分两种情况：

#### 已在观察列表中

- 更新 `open_info.price = 当日收盘价`
- 更新 `open_info.timestamp = 当前时间`
- 保存后 `continue`

见：`tokenDemo/autoTrade_pm.py:3131-3139`

这表示：

- **如果股票再次涨停，会刷新观察时间，延长观察期**

#### 不在观察列表中

则加入：

- `side = BUY`
- `strategy = []`
- `name = 股票名称`
- `price = 当日收盘价`
- `timestamp = 当前时间`

见：`tokenDemo/autoTrade_pm.py:3141-3148`

注意这里和 AUTOBN 不同：

- AUTOA 刚入观察列表时，`strategy` 是空列表
- 后续盘中满足不同条件时，才追加 `BZ` 或 `N`

---

## 3.3 AUTOA 从观察到开仓的总前提

代码位置：`tokenDemo/autoTrade_pm.py:2951`

### 3.3.1 观察期最长 30 天

要求：

- `today.timestamp() - open_info.timestamp <= OBSERVATION_TIMEOUT_SECONDS`
- `OBSERVATION_TIMEOUT_SECONDS = 30 * 24 * 60 * 60`

超时则直接从观察列表移除。见：`tokenDemo/autoTrade_pm.py:2969-2972`

### 3.3.2 同一 UTC 日期内不允许当日入观察、当日开仓

代码：`tokenDemo/autoTrade_pm.py:2973-2981`

如果：

- `today` 的 UTC 日期 == `open_info.timestamp` 的 UTC 日期

则直接 `return`。

这意味着：

- **当天收盘新加入观察列表的股票，不会在同一个 UTC 日期里立刻开仓**
- 必须至少等到下一次日期切换后再检查开仓

### 3.3.3 当天必须是阳线

要求：

- `hist_close[-1] > hist_open[-1]`

如果：

- `hist_close[-1] <= hist_open[-1]`

直接不考虑开仓。见：`tokenDemo/autoTrade_pm.py:2997-2999`

即：

- **AUTOA 的入场确认必须建立在当日上涨（收阳）基础上**

---

## 3.4 AUTOA 开仓确认条件一：放量跳空突破，追加 BZ

代码：`tokenDemo/autoTrade_pm.py:3001-3024`

按当前代码口径，这里已经拆成两套独立窗口：

- 最大量比较窗口：最近 `10` 根，即 `VOLUME_LOOKBACK_PERIOD = 10`
- 切比雪夫统计样本：`-30:-10`

即：

- `volume_sample = hist_volume[-30:-10]`
- `current_volume = hist_volume[-1]`
- `current_atr = calculate_atr(hist)`

接着同时满足以下条件时：

1. `hist_open[-1] > hist_high[-2]`
   - 今天开盘价高于昨天最高价
   - 即明显跳空高开
2. `current_volume >= max(hist_volume[-10:])`
   - 今日成交量至少达到最近 10 根中的最大值
3. `calculate_chebyshev_probability(volume_sample, current_volume)["chebyshev_upper_bound"] < CHEBYSHEV_EXTREME_THRESHOLD`
   - `CHEBYSHEV_EXTREME_THRESHOLD = 0.01`
   - 即今日成交量相对 `-30:-10` 这一段历史样本属于统计意义上的极端放量

满足后：

- 如果 `BZ` 还不在 `open_info.strategy` 中，则追加 `BZ`
- `should_open = True`

见：`tokenDemo/autoTrade_pm.py:3011-3024`

因此，这一类 AUTOA 开仓信号的本质是：

- **涨停池观察股，在后续交易日出现跳空高开 + 相对 `-30:-10` 样本极端放量 + 当前量达到最近 10 根最大值 + 阳线时开仓**

---

## 3.5 AUTOA 开仓确认条件二：10 日线下跳空高开，追加 N

这是一个依赖先前 BZ 标签的二段条件。代码：

- `tokenDemo/autoTrade_pm.py:3025-3030`
- `tokenDemo/autoTrade_pm.py:2383-2418`

### 3.5.1 前提：观察记录里已经有 BZ

要求：

- `PositionSide.BZ in open_info.strategy`

### 3.5.2 形态函数 `check_gap_up_after_break_ma10(hist)` 条件

函数内部要求：

1. 历史长度至少 `MA_PERIOD + 2`
   - `MA_PERIOD = 10`
2. 前两根 K 线（不含今天），即 `hist.iloc[-2]`、`hist.iloc[-3]`：
   - 收盘价都低于各自 10 日均线
3. 今天开盘价 `today_open > yesterday_high`
   - 即跳空高开

满足后返回 `True`。

### 3.5.3 条件成立时的处理

若：

- 已有 `BZ`
- 且 `check_gap_up_after_break_ma10(hist)` 为真

则：

- 若 `N` 不在策略中，追加 `N`
- `should_open = True`

这说明 `N` 更像一个“**BZ 之后的补充形态标签**”，不是独立观察入口。

---

## 3.6 AUTOA 真正建仓时的硬条件

当 `should_open` 为真后，还要继续满足：

- `current_atr > 0`

见：`tokenDemo/autoTrade_pm.py:3032`

也就是：

- **ATR 必须有效，AUTOA 才允许生成持仓**

随后执行：

1. `price_close = 今日收盘价`
2. `hl2 = (high + low) / 2`
3. `take_profit = hl2 + current_atr * SUPERTREND_FACTOR`
4. `stop_loss = hl2 - current_atr * SUPERTREND_FACTOR`

其中：

- `SUPERTREND_FACTOR = 3.0`

见：`tokenDemo/autoTrade_pm.py:3033-3037`

然后写入持仓：

- `position_side = LONG`
- `close_side = SELL`
- `entry_price = price_close`
- `date = today.strftime("%Y%m%d")`
- `strategy = open_info.strategy`

见：`tokenDemo/autoTrade_pm.py:3044-3053`

也就是说 AUTOA 的开仓本质上是：

- **确认信号成立后，以当日收盘价作为入场价建一个 LONG 虚拟持仓**
- **并按 ATR × 3 初始化止盈止损**

### 3.6.1 观察记录不会被删除，而是保留更新后的策略

代码：`tokenDemo/autoTrade_pm.py:3065-3066`

这里不是把 observation 删除，而是：

- `cls.alert_all["OBSERVATIONS"][code] = open_info.model_dump()`

因此可以理解为：

- AUTOA 开仓后，观察记录仍保留一份策略上下文
- 真正是否持仓由 `POSITIONS` 决定
- 后续 `filter_stocks()` 会优先跳过已在 `POSITIONS` 的 code，见 `tokenDemo/autoTrade_pm.py:3166-3171`

---

## 四、AUTOA 与 AUTOBN 开仓条件对比

## 4.1 共同点

两者的共同结构：

1. 先记录 `OBSERVATIONS`
2. 再通过更严格条件确认
3. 开仓后写入 `POSITIONS`
4. 都用 ATR / Supertrend 思路初始化止盈止损

共同的核心理念是：

- **先发现候选，再等待确认，不追求第一时间，而追求条件更完整的入场**

## 4.2 AUTOBN 更偏“衍生品数据确认”

AUTOBN 的开仓过滤更依赖：

- 多空比 `long_short_ratio`
- OI（5m / 1h / 1d）
- 切比雪夫极值统计
- 基差率 `basis_rate`
- 账户余额、杠杆、名义价值、健康度
- 24 小时重开冷却

所以 AUTOBN 的开仓条件是：

- **市场行为 + 衍生品结构 + 账户风控** 三层叠加

## 4.3 AUTOA 更偏“形态 + 量能确认”

AUTOA 的开仓过滤更依赖：

- 涨停池来源
- 次日/后续交易日阳线确认
- 跳空高开
- 极端放量
- 10 日线下方再跳空的形态修复
- ATR 是否可算

因此 AUTOA 的开仓条件本质上是：

- **题材股先入池，再等量价结构确认后建仓**

---

## 五、简版清单

## 5.1 AUTOBN 做多开仓清单

必须依次满足：

1. 先前被记录为 `BZ` 观察对象
2. 当前价格仍高于前一日收盘
3. 当前多空比 `< 1.5`
4. 当前多空比满足：极端低位或 `< 3/7`
5. `blend > long_ratio_5m`
6. 当前 5m OI ≥ 1h OI 样本最大值
7. OI 的切比雪夫上界 `< 0.01`
8. 24 小时内没有刚平仓
9. ATR 可计算，止盈止损有效
10. 可用余额、最小名义价值、保证金、账户健康度都达标

## 5.2 AUTOBN 做空开仓清单

必须依次满足：

1. 先前被记录为 `BD` 观察对象
2. 当前价格低于前一日收盘
3. 当前 5m OI ≤ 1d OI 样本最小值
4. OI 的切比雪夫上界 `< 0.05`
5. 24 小时内没有刚平仓
6. ATR 可计算，止盈止损有效
7. 可用余额、最小名义价值、保证金、账户健康度都达标

## 5.3 AUTOA 开仓清单

必须依次满足：

1. 该股此前由涨停池进入 `OBSERVATIONS`
2. 观察记录未超过 30 天
3. 不是观察当日就立刻开仓
4. 当天必须收阳
5. 历史成交量数据至少够 30 个样本
6. 满足以下任一类：
   - 跳空高开 + 当前量达到最近 10 根最大值 + 相对 `-30:-10` 样本极端放量 → 追加 `BZ`
   - 已有 `BZ` 且满足“10 日线下跳空高开” → 追加 `N`
7. ATR > 0
8. 用 `hl2 ± ATR × 3` 初始化止盈止损并写入持仓

---

## 六、关键代码位置索引

### AUTOBN

- 新建观察信号：`tokenDemo/autoTrade_pm.py:2020`
- 做多/做空确认：`tokenDemo/autoTrade_pm.py:1868`
- 方向过滤 `check_side()`：`tokenDemo/autoTrade_pm.py:1005`
- 真正下单 `open_bn_position()`：`tokenDemo/autoTrade_pm.py:719`
- 主调度入口：`tokenDemo/autoTrade_pm.py:2151`

### AUTOA

- 收盘加入观察列表：`tokenDemo/autoTrade_pm.py:3071`
- 观察转持仓：`tokenDemo/autoTrade_pm.py:2951`
- 10 日线下跳空高开判断：`tokenDemo/autoTrade_pm.py:2383`
- A 股主监控入口：`tokenDemo/autoTrade_pm.py:3221`

---

如果你要，我下一步可以继续把这份文档再补成两张表：

1. **AUTOBN 开仓决策树**
2. **AUTOA 开仓信号对照表（BZ / N / 观察 / 持仓）**
