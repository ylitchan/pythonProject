import pandas as pd

def calculate_ema_pandas(prices, period):
    """
    使用pandas计算EMA
    """
    df = pd.Series(prices)
    ema = df.ewm(span=period, adjust=False).mean()
    return ema.tolist()

# 示例使用
prices = [22.27, 22.19, 22.08, 22.17, 22.18,
          22.13, 22.23, 22.43, 22.24, 22.29,
          22.15, 22.39]
period = 12

ema_values = calculate_ema_pandas(prices, period)
print("价格数据:", prices)
print(f"{period}日EMA:", [round(x, 2) for x in ema_values])