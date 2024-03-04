"""
sigmoid 函数与阶跃函数图形
"""
import numpy as np
from matplotlib import pyplot as plt


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def step_function(x):
    """
    阶跃函数
    :param x: 入参
    :return:
    """
    return np.array(x > 0, dtype=np.int)


if __name__ == "__main__":
    # 在-5.0到5.0的范围内，以0.1位单位，生成Numpy数组array([-5.0, -4.9, ... , 4.8, 4.9])
    x = np.arange(-5.0, 5.0, 0.1)
    y1 = sigmoid(x)
    y2 = step_function(x)
    plt.plot(x, y1, label='sigmoid function')
    plt.plot(x, y2, label='step function')
    plt.ylim(-0.1, 1.1)  # 指定y轴的范围
    plt.legend(loc='best')
    plt.show()