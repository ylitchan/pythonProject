"""
切比雪夫概率计算演示脚本

演示切比雪夫概率的计算方法
"""


def calculate_chebyshev_probability(data_list, value):
    """
    计算给定数值对应的切比雪夫概率

    功能：根据切比雪夫不等式计算给定数值在数据分布中的概率特征

    切比雪夫不等式：P(|X - μ| >= kσ) <= 1/k²
    换言之：至少有 (1 - 1/k²) 的数据落在 [μ - kσ, μ + kσ] 区间内

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
    """
    # 输入验证
    if not data_list or len(data_list) == 0:
        raise ValueError("数据列表不能为空")

    if len(data_list) == 1:
        return {
            "mean": data_list[0],
            "std": 0.0,
            "k": float("inf") if data_list[0] != value else 0.0,
            "chebyshev_upper_bound": 0.0,
            "min_probability_in_range": 1.0,
            "deviation": value - data_list[0],
            "message": "数据只有一个元素，标准差为0",
        }

    # 计算均值
    mean = sum(data_list) / len(data_list)

    # 计算标准差（样本标准差，使用 n-1 作为分母）
    variance = sum((x - mean) ** 2 for x in data_list) / (len(data_list) - 1)
    std = variance**0.5

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


def demo_chebyshev_probability():
    """演示切比雪夫概率计算"""

    print("=" * 80)
    print("切比雪夫概率计算演示")
    print("=" * 80)

    # 示例1：价格数据
    print("\n【示例1：加密货币价格数据】")
    prices = [100, 102, 98, 101, 99, 103, 97, 105, 95, 100]
    test_value = 110

    print(f"价格列表: {prices}")
    print(f"测试数值: {test_value}")

    result = calculate_chebyshev_probability(prices, test_value)

    print(f"\n结果分析:")
    print(f"  均值 (μ): {result['mean']:.4f}")
    print(f"  标准差 (σ): {result['std']:.4f}")
    print(f"  偏差: {result['deviation']:.4f}")
    print(f"  标准差倍数 (k): {result['k']:.4f}")
    print(f"  切比雪夫上界: {result['chebyshev_upper_bound']:.4%}")
    print(f"  数据范围内最小概率: {result['min_probability_in_range']:.2%}")
    print(f"\n解释:")
    print(f"  {result['message']}")

    # 示例2：不同的测试值
    print("\n" + "=" * 80)
    print("【示例2：测试多个不同的数值】")
    test_values = [95, 100, 105, 110, 115]

    for test_val in test_values:
        result = calculate_chebyshev_probability(prices, test_val)
        print(f"\n测试值 {test_val}:")
        print(f"  距离均值 {result['k']:.2f} 个标准差")
        if result["k"] > 1:
            print(f"  超出范围的概率上界: {result['chebyshev_upper_bound']:.2%}")
        else:
            print(f"  在 1σ 范围内，切比雪夫不等式不适用")

    # 示例3：收益率数据
    print("\n" + "=" * 80)
    print("【示例3：日收益率数据】")
    returns = [0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.01, 0.04, -0.02, 0.01]
    extreme_return = 0.10  # 极端收益率

    print(f"收益率列表: {[f'{r:.2%}' for r in returns]}")
    print(f"极端收益率: {extreme_return:.2%}")

    result = calculate_chebyshev_probability(returns, extreme_return)

    print(f"\n结果分析:")
    print(f"  平均收益率: {result['mean']:.4%}")
    print(f"  收益率标准差: {result['std']:.4%}")
    print(f"  极端收益率是 {result['k']:.2f} 个标准差")
    print(f"\n解释:")
    print(f"  {result['message']}")

    # 示例4：实际应用场景
    print("\n" + "=" * 80)
    print("【示例4：风险评估实际应用】")
    print("\n场景：评估某个交易价格是否为异常值")
    recent_prices = [
        50000,
        51000,
        49500,
        50500,
        50200,
        49800,
        51200,
        50100,
        49900,
        50300,
    ]
    current_price = 55000

    print(f"最近10天价格: {recent_prices}")
    print(f"当前价格: {current_price}")

    result = calculate_chebyshev_probability(recent_prices, current_price)

    print(f"\n风险评估:")
    print(f"  历史均价: {result['mean']:.2f}")
    print(f"  价格波动(标准差): {result['std']:.2f}")
    print(f"  当前价格偏离均价: {result['deviation']:.2f}")
    print(f"  这是 {result['k']:.2f} 倍标准差的偏离")

    if result["k"] > 3:
        print(f"\n⚠️ 风险提醒：")
        print(f"  当前价格严重偏离历史均值（{result['k']:.2f}σ）")
        print(f"  这种极端偏离发生的概率上界仅为 {result['chebyshev_upper_bound']:.2%}")
        print(f"  建议谨慎交易！")
    elif result["k"] > 2:
        print(f"\n⚡ 警告：")
        print(f"  当前价格明显偏离历史均值（{result['k']:.2f}σ）")
        print(f"  需要密切关注市场动态")
    else:
        print(f"\n✓ 正常范围内")

    print("\n" + "=" * 80)
    print("演示完成！")
    print("\n说明：此方法已添加到 tokenDemo/autoBN.py 的 AUTOBN 类中")
    print("调用方式: autobn_instance.calculate_chebyshev_probability(data_list, value)")
    print("=" * 80)


if __name__ == "__main__":
    demo_chebyshev_probability()
