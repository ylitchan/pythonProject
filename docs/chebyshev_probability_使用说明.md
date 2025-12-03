# 切比雪夫概率计算方法使用说明

## 功能描述

`calculate_chebyshev_probability` 是一个用于计算给定数值在数据分布中的切比雪夫概率特征的方法。

该方法已添加到 `tokenDemo/autoBN.py` 文件的以下两个类中：
- **AUTOBN 类**: 实例方法，用于币安期货交易
- **AUTOA 类**: 类方法 (@classmethod)，用于A股交易

## 切比雪夫不等式简介

切比雪夫不等式（Chebyshev's inequality）是概率论中的一个重要定理，用于描述随机变量的分布特征：

**公式**: P(|X - μ| ≥ kσ) ≤ 1/k²

其中：
- X 是随机变量
- μ 是均值
- σ 是标准差
- k 是标准差的倍数

**意义**: 至少有 (1 - 1/k²) 的数据落在 [μ - kσ, μ + kσ] 区间内。

## 方法签名

### AUTOBN 类（实例方法）

```python
def calculate_chebyshev_probability(self, data_list, value):
    """
    计算给定数值对应的切比雪夫概率
    
    参数：
        data_list: 数据列表（如价格列表、收益率列表等）
        value: 给定的数值，用于计算其在分布中的位置
        
    返回：
        字典，包含以下信息：
        - mean: 数据均值
        - std: 数据标准差
        - k: 给定数值距离均值的标准差倍数
        - chebyshev_upper_bound: 切比雪夫不等式的上界概率 (1/k²)
        - min_probability_in_range: 至少有该比例的数据在 k 个标准差范围内 (1 - 1/k²)
        - deviation: 给定数值与均值的偏差
        - message: 人类可读的解释说明
    """
```

### AUTOA 类（类方法）

```python
@classmethod
def calculate_chebyshev_probability(cls, data, value):
    """
    计算给定数值对应的切比雪夫概率 (支持 pandas Series/DataFrame 和 list)
    
    参数：
        data: 数据集合，可以是 pandas.Series, pandas.DataFrame (单列) 或 list
        value: 给定的数值，用于计算其在分布中的位置
        
    返回：
        字典，包含信息与 AUTOBN 类相同
    """
```

## 使用示例

### AUTOBN 类示例

#### 示例1：分析价格异常

```python
# 假设您已经创建了 AUTOBN 实例
from tokenDemo.autoBN import AUTOBN

# 创建实例（需要提供必要的配置参数）
autobn = AUTOBN.from_cfg(qy_key="your_key", bn_api_file="bn.json")

# 历史价格数据
prices = [100, 102, 98, 101, 99, 103, 97, 105, 95, 100]

# 要评估的价格
test_price = 110

# 计算切比雪夫概率
result = autobn.calculate_chebyshev_probability(prices, test_price)

# 打印结果
print(f"均值: {result['mean']:.2f}")
print(f"标准差: {result['std']:.2f}")
print(f"测试价格距离均值 {result['k']:.2f} 个标准差")
print(f"解释: {result['message']}")
```

#### 示例2：风险评估

```python
# 近期收益率数据
returns = [0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.01, 0.04, -0.02, 0.01]

# 极端收益率
extreme_return = 0.10

# 计算概率
result = autobn.calculate_chebyshev_probability(returns, extreme_return)

# 风险评估
if result['k'] > 3:
    print(f"⚠️ 高风险警告: 超出 {result['k']:.2f} 个标准差!")
    print(f"发生概率上界: {result['chebyshev_upper_bound']:.2%}")
elif result['k'] > 2:
    print(f"⚡ 中等风险: 超出 {result['k']:.2f} 个标准差")
else:
    print("✓ 正常范围内")
```

#### 示例3：在交易策略中使用

```python
# 在 rzq_token 或其他交易方法中使用
async def check_price_anomaly(self, symbol, current_price, kline_close):
    """检查价格是否异常"""
    
    # 使用历史收盘价数据
    result = self.calculate_chebyshev_probability(kline_close, current_price)
    
    # 如果价格偏离超过3个标准差，发送警告
    if result['k'] > 3:
        msg = (
            f"{symbol} 价格异常\\n"
            f"当前价格: {current_price}\\n"
            f"历史均价: {result['mean']:.2f}\\n"
            f"偏离程度: {result['k']:.2f}σ\\n"
            f"异常概率上界: {result['chebyshev_upper_bound']:.2%}"
        )
        self.send_msg(msg)
        return True
    
    return False
```

### AUTOA 类示例

#### 示例1：A股成交量分析

```python
from tokenDemo.autoBN import AUTOA

# 注意：AUTOA 的方法是类方法，直接通过类名调用，无需创建实例

# 历史成交量数据
volumes = [1000000, 1200000, 950000, 1100000, 1050000, 1300000, 980000, 1150000]

# 当前成交量
current_volume = 2500000

# 计算切比雪夫概率
result = AUTOA.calculate_chebyshev_probability(volumes, current_volume)

# 打印结果
print(f"平均成交量: {result['mean']:.0f}")
print(f"成交量标准差: {result['std']:.0f}")
print(f"当前成交量偏离 {result['k']:.2f} 个标准差")

if result['k'] > 2:
    print(f"⚠️ 成交量异常，发生概率上界: {result['chebyshev_upper_bound']:.2%}")
```

#### 示例2：股价波动分析

```python
# 近期股价数据
prices = [10.5, 10.8, 10.3, 10.6, 10.4, 10.9, 10.2, 10.7]

# 目标价格
target_price = 12.0

# 计算切比雪夫概率
result = AUTOA.calculate_chebyshev_probability(prices, target_price)

if result['k'] > 3:
    print("💡 投资建议: 目标价格设定可能过于激进")
elif result['k'] > 2:
    print("💡 投资建议: 目标价格合理但需要密切关注")
else:
    print("💡 投资建议: 目标价格在正常波动范围内")
```

#### 示例3：在A股监控策略中使用

```python
@classmethod
def check_volume_anomaly(cls, code, hist_data):
    """检查成交量是否异常"""
    
    # 提取历史成交量
    volumes = hist_data['volume'].tolist()
    current_volume = volumes[-1]
    historical_volumes = volumes[:-1]
    
    # 计算切比雪夫概率
    result = cls.calculate_chebyshev_probability(historical_volumes, current_volume)
    
    # 成交量异常判断
    if result['k'] > 3:
        msg = (
            f"股票 {code} 成交量异常\\n"
            f"当前成交量: {current_volume:.0f}\\n"
            f"平均成交量: {result['mean']:.0f}\\n"
            f"偏离程度: {result['k']:.2f}σ\\n"
            f"异常概率上界: {result['chebyshev_upper_bound']:.2%}"
        )
        cls.send_msg(msg)
        return True
    
    return False
```

## 返回值详解

方法返回一个字典，包含以下字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `mean` | float | 数据均值 (μ) |
| `std` | float | 数据标准差 (σ) |
| `k` | float | 给定数值距离均值的标准差倍数 |
| `deviation` | float | 给定数值与均值的偏差 (value - mean) |
| `chebyshev_upper_bound` | float | 切比雪夫不等式的上界概率，即超出k个标准差范围的概率上界 (1/k²) |
| `min_probability_in_range` | float | 至少有该比例的数据在k个标准差范围内 (1 - 1/k²) |
| `message` | str | 人类可读的解释说明 |

## 应用场景

1. **价格异常检测**: 判断当前价格是否偏离历史均值过大
2. **风险评估**: 评估极端收益率出现的概率
3. **止盈止损设置**: 基于历史波动设置合理的止盈止损位
4. **交易信号过滤**: 过滤掉统计上不太可能的交易信号
5. **市场异常监控**: 实时监控市场是否出现异常波动

## 注意事项

1. **数据量要求**: 至少需要2个数据点，建议使用10个以上的数据点以获得更准确的结果
2. **k值限制**: 当 k ≤ 1 时，切比雪夫不等式不提供有用信息（上界为1）
3. **分布无关性**: 切比雪夫不等式适用于任何概率分布，不假设数据服从正态分布
4. **保守估计**: 切比雪夫不等式给出的是保守的上界，实际概率可能更小

## 数学背景

### 当 k = 2 时：
- 至少 75% 的数据落在 [μ - 2σ, μ + 2σ] 范围内
- 超出此范围的数据不超过 25%

### 当 k = 3 时：
- 至少 88.89% 的数据落在 [μ - 3σ, μ + 3σ] 范围内
- 超出此范围的数据不超过 11.11%

### 当 k = 4 时：
- 至少 93.75% 的数据落在 [μ - 4σ, μ + 4σ] 范围内
- 超出此范围的数据不超过 6.25%

## 测试示例

### AUTOBN 类测试

可以运行项目根目录下的 `test_chebyshev.py` 文件查看完整的演示示例：

```bash
uv run python test_chebyshev.py
```

该脚本演示了多个实际应用场景，包括：
- 加密货币价格数据分析
- 多个测试值的比较
- 日收益率数据分析
- 风险评估实际应用

### AUTOA 类测试

可以运行项目根目录下的 `test_autoa_chebyshev.py` 文件查看 A股相关的演示示例：

```bash
uv run python test_autoa_chebyshev.py
```

该脚本演示了 A股交易中的应用场景，包括：
- A股成交量数据分析
- 股价波动分析
- 涨跌幅分析

## 相关方法

与此方法配合使用的其他统计方法：
- `calculate_atr()`: 计算平均真实波幅（ATR）
- `calc_stop_profit_loss()`: 基于ATR计算止盈止损位

## 更新日期

2025-11-30

## 更新记录

- 2025-11-30: 初始版本，添加到 AUTOBN 类和 AUTOA 类
