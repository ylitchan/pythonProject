"""
迁移脚本：将旧版 alert JSON 文件转换为新版 Pydantic 模型格式

变更内容：
1. OBSERVATIONS: 从列表 [price, timestamp, side, strategy] 转换为 Observation 模型字典
2. POSITIONS: 从列表转换为 Position 模型字典，并添加 tp_count: 0 字段

使用方法：
    uv run python tokenDemo/migrate_alert_json.py
"""

import json
import os
from pathlib import Path


def migrate_observation(
    symbol_or_code: str, data: list, is_a_stock: bool = False
) -> dict:
    """
    将旧版 Observation 列表转换为新版字典格式

    旧格式 (BN):  [price, timestamp, side, strategy]
    旧格式 (A股): [price, timestamp, name, strategy]
    新格式: {price, timestamp, side, strategy: [PositionSide], name}
    """
    if isinstance(data, dict):
        # 已经是新格式，跳过
        return data

    if is_a_stock:
        # A股格式: [price, timestamp, name, strategy]
        return {
            "price": data[0],
            "timestamp": data[1],
            "side": "BUY",  # A股默认买入
            "strategy": [data[3]] if isinstance(data[3], str) else data[3],
            "name": data[2],  # 股票名称
        }
    else:
        # BN格式: [price, timestamp, side, strategy]
        strategy_value = data[3] if len(data) > 3 else "BZ"
        # 处理旧版策略标签 (如 "BZ1", "BZ2" -> "BZ")
        if isinstance(strategy_value, str):
            if strategy_value.startswith("BZ"):
                strategy_value = "BZ"
            elif strategy_value.startswith("BD"):
                strategy_value = "BD"
            strategy_value = [strategy_value]

        return {
            "price": data[0],
            "timestamp": data[1],
            "side": data[2],
            "strategy": strategy_value,
            "name": symbol_or_code,  # BN 使用 symbol 作为 name
        }


def migrate_position(
    symbol_or_code: str, data: list | dict, is_a_stock: bool = False
) -> dict:
    """
    将旧版 Position 列表转换为新版字典格式，并添加 tp_count

    旧格式 (BN):  [take_profit, stop_loss, close_side, position_side, entry_price]
    旧格式 (A股): [take_profit, stop_loss, name, date, entry_price, strategy]
    新格式: {take_profit, stop_loss, close_side, position_side, entry_price, name, date, strategy, tp_count}
    """
    if isinstance(data, dict):
        # 已经是字典格式，只需确保有 tp_count 字段
        if "tp_count" not in data:
            data["tp_count"] = 0
        return data

    if is_a_stock:
        # A股格式: [take_profit, stop_loss, name, date, entry_price, strategy]
        strategy_value = data[5] if len(data) > 5 else "Supertrend"
        return {
            "take_profit": data[0],
            "stop_loss": data[1],
            "close_side": "SELL",  # A股默认卖出平仓
            "position_side": "LONG",  # A股只能做多
            "entry_price": data[4] if len(data) > 4 else 0.0,
            "name": data[2],  # 股票名称
            "date": data[3] if len(data) > 3 else 0,  # 日期
            "strategy": [strategy_value] if isinstance(strategy_value, str) else strategy_value,
            "tp_count": 0,
        }
    else:
        # BN格式: [价格1, 价格2, close_side, position_side, entry_price, ...]
        # 对于 LONG: 价格1=止盈(高), 价格2=止损(低) -> 直接使用
        # 对于 SHORT: 价格1=止损(高), 价格2=止盈(低) -> 需要交换
        position_side = data[3]
        if position_side == "SHORT":
            # 空头仓位：止盈应低于入场价，止损应高于入场价
            take_profit = data[1]  # 较低的价格作为止盈
            stop_loss = data[0]  # 较高的价格作为止损
        else:
            # 多头仓位：止盈应高于入场价，止损应低于入场价
            take_profit = data[0]  # 较高的价格作为止盈
            stop_loss = data[1]  # 较低的价格作为止损

        return {
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "close_side": data[2],
            "position_side": position_side,
            "entry_price": data[4] if len(data) > 4 else 0.0,
            "name": symbol_or_code,
            "date": 0,  # 旧版没有日期，设为0
            "strategy": [position_side],  # 使用 position_side 作为策略
            "tp_count": 0,  # 新增字段，默认为0
        }


def migrate_file(file_path: str, is_a_stock: bool = False) -> None:
    """迁移单个 JSON 文件"""
    print(f"正在迁移: {file_path}")

    # 备份原文件
    backup_path = file_path + ".bak"
    if not os.path.exists(backup_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  已创建备份: {backup_path}")

    # 读取并转换数据
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 迁移 OBSERVATIONS
    if "OBSERVATIONS" in data:
        new_observations = {}
        for key, value in data["OBSERVATIONS"].items():
            new_observations[key] = migrate_observation(key, value, is_a_stock)
        data["OBSERVATIONS"] = new_observations
        print(f"  已迁移 {len(new_observations)} 个 OBSERVATIONS")

    # 迁移 POSITIONS
    if "POSITIONS" in data:
        new_positions = {}
        for key, value in data["POSITIONS"].items():
            new_positions[key] = migrate_position(key, value, is_a_stock)
        data["POSITIONS"] = new_positions
        print(f"  已迁移 {len(new_positions)} 个 POSITIONS")

    # 写回文件
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"  迁移完成!")


def main():
    """主函数"""
    current_dir = Path(__file__).parent

    # 迁移 BN 文件
    bn_file = current_dir / "alert_all.json"
    if bn_file.exists():
        migrate_file(str(bn_file), is_a_stock=False)

    # 迁移 A股 文件
    a_file = current_dir / "alert_all_A.json"
    if a_file.exists():
        migrate_file(str(a_file), is_a_stock=True)

    print("\n所有文件迁移完成!")


if __name__ == "__main__":
    main()
