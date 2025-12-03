"""
测试 AUTOA 类的切比雪夫概率计算方法

这个脚本独立测试 AUTOA.calculate_chebyshev_probability 方法
"""

import pandas as pd


def calculate_chebyshev_probability(data, value):
    """
    计算给定数值对应的切比雪夫概率 (支持 pandas Series/DataFrame 和 list)

    这是从 AUTOA 类复制的方法，用于独立测试
    """
    # 统一转换为 pandas Series 处理
    if isinstance(data, list):
        series = pd.Series(data)
    elif isinstance(data, pd.DataFrame):
        if data.shape[1] != 1:
            series = data.iloc[:, 0]
        else:
            series = data.iloc[:, 0]
    elif isinstance(data, pd.Series):
        series = data
    else:
        try:
            series = pd.Series(data)
        except Exception:
            raise ValueError(
                "不支持的数据类型，请提供 list, pandas.Series 或 pandas.DataFrame"
            )

    # 输入验证
    if series.empty:
        raise ValueError("数据不能为空")

    # 处理单元素情况
    if len(series) == 1:
        item = float(series.iloc[0])
        return {
            "mean": item,
            "std": 0.0,
            "k": float("inf") if item != value else 0.0,
            "chebyshev_upper_bound": 0.0,
            "min_probability_in_range": 1.0,
            "deviation": value - item,
            "message": "数据只有一个元素，标准差为0",
        }

    # 利用 pandas 向量化计算均值和标准差
    mean = float(series.mean())
    std = float(series.std(ddof=1))  # 样本标准差

    # 计算给定数值与均值的偏差
    deviation = value - mean

    # 如果标准差为0（所有数据相同）
    if std == 0:
        return {
            "mean": mean,
            "std": 0.0,
            "k": float("inf") if deviation != 0 else 0.0,
            "chebyshev_upper_bound": 0.0,
            "min_probability_in_range": 1.0,
            "deviation": deviation,
            "message": "所有数据相同，标准差为0",
        }

    # 计算 k 值（给定数值距离均值有多少个标准差）
    k = abs(deviation) / std

    # 切比雪夫不等式的上界：P(|X - μ| >= kσ) <= 1/k²
    # 只有当 k > 1 时，切比雪夫不等式才有意义
    if k <= 1:
        chebyshev_upper_bound = 1.0  # k <= 1 时，不等式给出的上界为 1（无信息）
        min_probability_in_range = 0.0
    else:
        chebyshev_upper_bound = 1 / (k**2)
        # 至少有 (1 - 1/k²) 的数据落在 [μ - kσ, μ + kσ] 区间内
        min_probability_in_range = 1 - chebyshev_upper_bound

    result = {
        "mean": mean,
        "std": std,
        "k": k,
        "chebyshev_upper_bound": chebyshev_upper_bound,
        "min_probability_in_range": min_probability_in_range,
        "deviation": deviation,
    }

    # 添加人类可读的解释
    if k <= 1:
        result["message"] = (
            f"数值 {value:.4f} 距离均值 {mean:.4f} 只有 {k:.4f} 个标准差（在 1σ 范围内），切比雪夫不等式不提供有用信息"
        )
    else:
        result["message"] = (
            f"数值 {value:.4f} 距离均值 {mean:.4f} 约 {k:.4f} 个标准差。"
            f"根据切比雪夫不等式，至少有 {min_probability_in_range:.2%} 的数据"
            f"落在 [μ - {k:.4f}σ, μ + {k:.4f}σ] 范围内，"
            f"即 [{mean - k * std:.4f}, {mean + k * std:.4f}] 区间。"
            f"超出此范围的数据比例不超过 {chebyshev_upper_bound:.2%}。"
        )

    return result


def test_autoa_chebyshev():
    """测试 AUTOA 类的切比雪夫概率计算方法"""

    print("=" * 80)
    print("AUTOA 类切比雪夫概率计算测试")
    print("=" * 80)

    # 测试1：A股成交量数据 (List)
    print("\n【测试1：A股成交量数据分析 (List)】")
    volumes = [
        1000000,
        1200000,
        950000,
        1100000,
        1050000,
        1300000,
        980000,
        1150000,
        1020000,
        1180000,
    ]
    extreme_volume = 2500000  # 极端成交量

    print(f"成交量列表: {volumes}")
    print(f"极端成交量: {extreme_volume}")

    result = calculate_chebyshev_probability(volumes, extreme_volume)

    print(f"\n结果分析:")
    print(f"  平均成交量: {result['mean']:.0f}")
    print(f"  成交量标准差: {result['std']:.0f}")
    print(f"  极端成交量偏离: {result['deviation']:.0f}")
    print(f"  标准差倍数 (k): {result['k']:.2f}")

    if result["k"] > 2:
        print(f"\n⚠️ 成交量异常：")
        print(f"  该成交量超出正常范围 {result['k']:.2f} 个标准差")
        print(f"  发生概率上界: {result['chebyshev_upper_bound']:.2%}")

    # 测试2：Pandas Series 数据
    print("\n" + "=" * 80)
    print("【测试2：Pandas Series 数据分析】")

    # 创建一个 Pandas Series
    prices_series = pd.Series(
        [10.5, 10.8, 10.3, 10.6, 10.4, 10.9, 10.2, 10.7, 10.5, 10.6]
    )
    target_price = 12.0

    print(f"Pandas Series:\n{prices_series.values}")
    print(f"目标价格: {target_price}")

    # 直接传入 Series
    result = calculate_chebyshev_probability(prices_series, target_price)

    print(f"\n结果分析:")
    print(f"  平均股价: {result['mean']:.2f}")
    print(f"  价格波动(标准差): {result['std']:.2f}")
    print(f"  目标价距离均价: {result['deviation']:.2f}")
    print(f"  标准差倍数: {result['k']:.2f}")

    if result["k"] > 3:
        print("\n💡 投资建议: 目标价格设定可能过于激进")
    elif result["k"] > 2:
        print("\n💡 投资建议: 目标价格合理但需要密切关注")
    else:
        print("\n💡 投资建议: 目标价格在正常波动范围内")

    # 测试3：Pandas DataFrame 数据
    print("\n" + "=" * 80)
    print("【测试3：Pandas DataFrame 数据分析】")

    df = pd.DataFrame(
        {
            "change": [0.02, -0.01, 0.03, -0.02, 0.01, -0.03, 0.02, 0.04, -0.01, 0.01],
            "volume": [100, 120, 90, 110, 105, 130, 95, 115, 100, 110],
        }
    )
    extreme_change = 0.08  # 极端涨幅

    print(f"DataFrame 'change' 列:\n{df['change'].values}")
    print(f"极端涨幅: {extreme_change:.2%}")

    # 传入 DataFrame 的一列 (Series)
    result = calculate_chebyshev_probability(df["change"], extreme_change)

    print(f"\n结果分析:")
    print(f"  平均涨跌幅: {result['mean']:.2%}")
    print(f"  波动率(标准差): {result['std']:.2%}")
    print(f"  极端涨幅是 {result['k']:.2f} 个标准差")

    if result["k"] > 2:
        print(f"\n📊 统计分析:")
        print(f"  这种涨幅非常罕见")
        print(f"  超出此范围的概率上界: {result['chebyshev_upper_bound']:.2%}")

    print("\n" + "=" * 80)
    print("测试完成！")
    print("\n说明：")
    print("- AUTOA 类的 calculate_chebyshev_probability 方法已优化")
    print("- 现在支持 list, pandas.Series 和 pandas.DataFrame")
    print("=" * 80)


if __name__ == "__main__":
    test_autoa_chebyshev()
