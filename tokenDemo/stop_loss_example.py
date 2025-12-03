#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
币安期货止盈止损单使用示例

本文件展示了如何使用AUTOBN类中的止盈止损功能
"""

from autoBN import AUTOBN

def example_usage():
    """使用示例"""
    
    # 初始化AUTOBN实例
    autobn = AUTOBN.from_cfg(
        bn_api_file='bn.json',
        alert_all_file='alert_all.json',
        qy_key='your_qy_key_here'
    )
    
    symbol = 'BTCUSDT'
    quantity = 0.001  # 交易数量
    
    print("=== 币安期货止盈止损单使用示例 ===\n")
    
    # 示例1：为现有持仓设置止损单
    print("1. 为现有持仓设置止损单")
    autobn.set_stop_loss_for_existing_position(
        symbol=symbol,
        positionSide='LONG',  # 多头持仓
        stop_loss_percent=0.03  # 3%止损
    )
    
    # 示例2：单独设置止损单
    print("\n2. 单独设置止损单")
    autobn.place_stop_loss_order(
        symbol=symbol,
        side='SELL',  # 平仓方向
        quantity=quantity,
        stop_price=50000,  # 止损触发价格
        stop_limit_price=49900  # 止损限价（可选）
    )
    
    # 示例3：单独设置止盈单
    print("\n3. 单独设置止盈单")
    autobn.place_take_profit_order(
        symbol=symbol,
        side='SELL',  # 平仓方向
        quantity=quantity,
        price=55000  # 止盈价格
    )
    
    # 示例4：使用OCO订单同时设置止盈和止损
    print("\n4. 使用OCO订单同时设置止盈和止损")
    autobn.place_oco_order(
        symbol=symbol,
        side='SELL',  # 平仓方向
        quantity=quantity,
        stop_price=50000,  # 止损触发价格
        stop_limit_price=49900,  # 止损限价
        price=55000  # 止盈价格
    )

def manual_trading_example():
    """手动交易示例"""
    
    autobn = AUTOBN.from_cfg(
        bn_api_file='bn.json',
        alert_all_file='alert_all.json',
        qy_key='your_qy_key_here'
    )
    
    symbol = 'ETHUSDT'
    
    print("=== 手动交易示例 ===\n")
    
    # 步骤1：开仓
    print("1. 开仓操作")
    result = autobn.open_bn_position(
        symbol=symbol,
        side='BUY',  # 买入开多
        positionSide='LONG',  # 多头持仓
        open_ratio=0.1  # 使用10%资金
    )
    
    if result:
        print(f"{symbol} 开仓成功")
        
        # 步骤2：手动设置止盈止损（如果自动设置失败）
        print("\n2. 手动设置止盈止损")
        
        # 获取当前价格
        mark_price_data = autobn.um_futures_client.mark_price(symbol)
        current_price = float(mark_price_data['markPrice'])
        
        # 设置3%止盈，3%止损
        take_profit_price = current_price * 1.03
        stop_loss_price = current_price * 0.97
        
        # 获取持仓数量
        amount = autobn.get_amount_close(symbol)
        
        if amount > 0:
            # 设置止盈单
            autobn.place_take_profit_order(
                symbol=symbol,
                side='SELL',
                quantity=amount,
                price=take_profit_price
            )
            
            # 设置止损单
            autobn.place_stop_loss_order(
                symbol=symbol,
                side='SELL',
                quantity=amount,
                stop_price=stop_loss_price
            )
            
            print(f"止盈价格: {take_profit_price}")
            print(f"止损价格: {stop_loss_price}")
            print(f"持仓数量: {amount}")
    else:
        print(f"{symbol} 开仓失败")

if __name__ == "__main__":
    # 运行示例
    example_usage()
    
    print("\n" + "="*50 + "\n")
    
    # 运行手动交易示例
    manual_trading_example()

