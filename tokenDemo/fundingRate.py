# ==================================================================================================
# 文件名: fundingRate.py
# 功能描述: 币安(Binance)和Drift交易所的资金费率套利工具
#   1. 监控两个交易所之间的资金费率差异
#   2. 在资金费率为负时自动开仓做多空组合（币安做空，Drift做多）
#   3. 监控账户健康度和风险管理
#   4. 定期导出资金费率数据分析报告
# 作者: ylitchan
# 创建日期: 2024
# 最后修改: 2025-05-30
# ==================================================================================================

import asyncio
import json
import logging
import time
import traceback
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from io import BytesIO

import pandas as pd
import requests
from anchorpy import Wallet
from binance.lib.utils import config_logging
from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient
from driftpy.constants import BASE_PRECISION, PERCENTAGE_PRECISION_EXP, QUOTE_PRECISION
from driftpy.constants.perp_markets import mainnet_perp_market_configs
from driftpy.drift_client import DriftClient
from driftpy.events.event_subscriber import EventSubscriber
from driftpy.events.types import EventSubscriptionOptions, WebsocketLogProviderConfig
from driftpy.events.types import WrappedEvent
from driftpy.math.margin import MarginCategory
from driftpy.types import OrderParams, OrderType, MarketType, PerpPosition
from driftpy.types import PositionDirection
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair


async def main():
    """
    主函数：资金费率套利系统的入口点

    该函数初始化系统配置和连接，设置事件监听，并启动定期健康度检查循环。
    整体架构包括：
    1. 配置交易参数和风险管理阈值
    2. 初始化币安和Drift的API连接
    3. 设置事件订阅和回调处理
    4. 启动定期健康度监控
    5. 处理费率报表生成和导出

    整个系统运行流程：
    - 监听Drift资金费率事件 -> 发现负费率机会 -> 在两个平台开对冲仓位 -> 赚取费率差价
    - 定期检查账户健康度 -> 必要时减仓或发出警告
    - 每日导出费率数据报表进行分析
    """
    # 交易参数配置
    symbol = 'ETHUSDT'  # 交易对
    market_index = 2  # Drift市场索引
    leverage = 6  # 杠杆倍数
    size_min = 0.1  # 最小交易数量
    size_max = 0.3  # 最大交易数量
    health4open = 80  # 开仓所需最低健康度
    health4close = 30  # 触发减仓的健康度阈值
    health4transfer = 70  # 触发警告的健康度阈值
    positionClose = 4 / 8  # 减仓比例
    global health_sleep
    health_sleep = 300  # 健康度检查间隔（秒）

    # 市场索引和映射配置
    perp_market_indexes = {market_index, 2}  # 需要订阅的永续合约市场
    spot_market_indexes = {0, }  # 需要订阅的现货市场
    open_map = {"SHORT": "SELL", "LONG": "BUY"}  # 开仓方向映射
    close_map = {"SHORT": "BUY", "LONG": "SELL"}  # 平仓方向映射
    # 创建市场索引到交易对名称的映射
    perp_market_indexes_symbol = {i.market_index: i.base_asset_symbol for i in mainnet_perp_market_configs}
    config_logging(logging, logging.INFO)
    with open(r'bn.json', 'r') as f:
        bn_api = json.load(f)
    session = requests.Session()
    session.headers = {'Content-Type': 'application/json'}
    um_futures_client = UMFutures(key=bn_api.get('api_key'), secret=bn_api.get('api_secret'))
    listenKey = um_futures_client.new_listen_key()["listenKey"]
    logging.info("Listen key : {}".format(listenKey))
    sp = {i['symbol']: i['quantityPrecision'] for i in um_futures_client.exchange_info()['symbols']}
    quantityPrecision = sp.get(symbol)
    if quantityPrecision == 0:
        quantityPrecision = Decimal('1')
    else:
        quantityPrecision = Decimal(f'0.{"1" * quantityPrecision}')
    url = 'https://mainnet.helius-rpc.com/?api-key=346cd7c9-73a9-4916-a150-4157181b99dc'  # replace w/ any rpc
    connection = AsyncClient(url)
    with open('PRIVATE_KEY', 'r') as f:
        PRIVATE_KEY = f.read()
    wallet = Wallet(Keypair.from_base58_string(PRIVATE_KEY))
    drift_client = DriftClient(connection, wallet, "mainnet", perp_market_indexes=[],
                               spot_market_indexes=[])
    # 4. 订阅账户数据
    await drift_client.unsubscribe()
    await drift_client.subscribe()
    # 获取当前用户账户
    drift_user = drift_client.get_user()
    for spot_position in drift_user.get_user_account().spot_positions:
        spot_market_indexes.add(spot_position.market_index)
    for perp_position in drift_user.get_user_account().perp_positions:
        perp_market_indexes.add(perp_position.market_index)
    drift_client.account_subscriber = drift_client.account_subscription_config.get_drift_client_subscriber(
        drift_client.program, list(perp_market_indexes), list(spot_market_indexes), oracle_infos=None
    )
    await drift_client.unsubscribe()
    await drift_client.subscribe()
    # 配置事件订阅
    options = EventSubscriptionOptions(
        event_types=('FundingRateRecord', 'LiquidationRecord'),
        max_tx=4096,
        max_events_per_type=4096,
        order_by="blockchain",
        order_dir="asc",
        log_provider_config=WebsocketLogProviderConfig()
    )
    event_subscriber = EventSubscriber(connection, drift_client.program, options)
    event_subscriber.unsubscribe()
    event_subscriber.subscribe()

    def send_msg(msg):
        """
        发送消息到企业微信群聊

        将程序运行状态、交易信号和警报通过企业微信机器人发送到指定群聊，
        同时在控制台打印消息内容和时间戳。

        :param msg: 要发送的消息内容
        :return: None
        """
        try:
            print(datetime.now(), msg)  # 同时在控制台打印消息
            json_msg = {
                "msgtype": "text",
                "text": {'content': msg}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=ee6e64f7-4423-47d0-9f9c-583298d7ae02',
                json=json_msg)
        except:
            return  # 发送失败时静默处理

    def calculate_health_drift(base_asset_amount=0) -> int:
        """
        计算Drift协议账户的健康度（健康百分比）

        该函数计算当前账户风险水平，考虑现有头寸以及假设的新增头寸。
        健康度计算公式：(1 - 维持保证金/总抵押品) * 100%

        :param base_asset_amount: 假设新增头寸的资产数量，默认为0（不考虑新增头寸）
        :return: 账户健康度，范围为0-100的整数，100表示最健康，0表示已清算
        """
        # 检查账户是否已经处于清算状态
        if drift_user.is_being_liquidated():
            return 0

        # 获取账户总抵押品价值和当前维持保证金要求
        total_collateral = drift_user.get_total_collateral(MarginCategory.MAINTENANCE)
        maintenance_margin_req = drift_user.get_margin_requirement(MarginCategory.MAINTENANCE)

        # 创建一个模拟的新增头寸对象，用于计算新增头寸的影响
        perp_position_cal = PerpPosition(
            last_cumulative_funding_rate=1063537496050, base_asset_amount=base_asset_amount,
            quote_asset_amount=-4829573078,
            quote_break_even_amount=-4801819309, quote_entry_amount=-4797405660, open_bids=0, open_asks=0,
            settled_pnl=94090387, lp_shares=0, last_base_asset_amount_per_lp=0, last_quote_asset_amount_per_lp=0,
            remainder_base_asset_amount=0, market_index=market_index, open_orders=0, per_lp_base=0
        )

        # 计算新增头寸带来的额外负债价值
        base_asset_value_cal = drift_user.calculate_weighted_perp_position_liability(
            perp_position=perp_position_cal,
            margin_category=MarginCategory.MAINTENANCE,
            liquidation_buffer=0,
            include_open_orders=False,
            strict=False,
        )

        # 计算总维持保证金要求
        maintenance_margin_req += base_asset_value_cal

        # 计算健康度
        if maintenance_margin_req == 0 and total_collateral >= 0:
            return 100  # 无维持保证金要求且有正抵押品，健康度100%
        elif total_collateral <= 0:
            return 0  # 抵押品为负，已清算
        else:
            return round(
                min(100, max(0, (1 - maintenance_margin_req / total_collateral) * 100))
            )

    def calculate_health_bn(notional) -> int:
        """
        计算Binance合约账户的健康度（健康百分比）

        该函数计算当前账户风险水平，考虑现有头寸以及假设的新增头寸。
        健康度计算公式：(1 - 维持保证金总额/账户总余额) * 100%

        :param notional: 假设新增头寸的名义价值，用于计算额外需要的维持保证金
        :return: 账户健康度，范围为0-100的整数，100表示最健康，0表示已爆仓
        """
        account_data = um_futures_client.account()
        # 总账户余额（可用保证金 + 已占用保证金）
        total_balance = float(account_data['totalMarginBalance'])
        position_data = um_futures_client.get_position_risk()
        total_maintenance_margin = 0.0

        # 计算现有头寸的维持保证金
        for position in position_data:
            # 只考虑有持仓的头寸（positionAmt 不为 0）
            if float(position['positionAmt']) != 0:
                maintenance_margin = float(position['maintMargin'])  # 维持保证金
                total_maintenance_margin += maintenance_margin

        # 加上新增头寸的维持保证金（假设维持保证金率为0.4%）
        total_maintenance_margin += notional * 0.004

        # 计算健康度
        if total_maintenance_margin == 0 and total_balance >= 0:
            return 100  # 无维持保证金要求且有正余额，健康度100%
        elif total_balance <= 0:
            return 0  # 余额为负，已爆仓
        else:
            # 保证金比例 = 维持保证金 / 账户余额 × 100%
            return round(
                min(100, max(0, (1 - total_maintenance_margin / total_balance) * 100))
            )

    def get_amount_close():
        """
        计算需要平仓的数量，用于平衡Binance和Drift之间的头寸

        该函数比较两个平台上的持仓数量，并确定需要在每个平台上关闭的数量，以便:
        1. 如果两个平台持仓数量相同，则在两边都减少持仓的positionClose比例
        2. 如果两个平台持仓数量不同，则减少持仓数量较多的平台上的持仓，使两边平衡

        :return: 包含需要在各平台平仓数量的字典 {'drift': float, 'bn': float}
        """
        try:
            # 获取Binance上的持仓数量
            position = um_futures_client.get_position_risk()
            position = position[0]
            positionAmt = abs(float(position['positionAmt'])) * BASE_PRECISION  # 转换为内部精度

            # 获取Drift上的持仓数量
            perp_position = drift_user.get_perp_position(market_index)
            base_asset_amount = abs(perp_position.base_asset_amount)

            # 情况1: 两个平台持仓数量相同 - 两边同时减仓
            if base_asset_amount == positionAmt:
                amount = float(Decimal(str(positionAmt * positionClose / BASE_PRECISION)).quantize(quantityPrecision,
                                                                                                   rounding=ROUND_DOWN))
                return {'drift': amount, 'bn': amount}
            # 情况2: Drift持仓多于Binance - 减少Drift端的持仓
            elif base_asset_amount > positionAmt:
                amount = float(
                    Decimal(str((base_asset_amount - positionAmt) / BASE_PRECISION)).quantize(quantityPrecision,
                                                                                              rounding=ROUND_DOWN))
                return {'drift': amount, 'bn': 0}
            # 情况3: Binance持仓多于Drift - 减少Binance端的持仓
            else:
                amount = float(
                    Decimal(str((positionAmt - base_asset_amount) / BASE_PRECISION)).quantize(quantityPrecision,
                                                                                              rounding=ROUND_DOWN))
                return {'drift': 0, 'bn': amount}
        except:
            # 出错时返回零值
            return {'drift': 0, 'bn': 0}

    def get_amount_open():
        """
        计算可开仓的数量，根据两个平台的余额和健康度限制

        该函数计算在确保账户安全的情况下，可以开仓的最大数量。计算步骤：
        1. 检查杠杆是否超过限制
        2. 获取两个平台的可用余额，取较小值确保平衡
        3. 根据杠杆和当前价格计算可开仓数量
        4. 确保开仓后账户健康度不低于安全阈值

        :return: 可开仓的数量，如果不满足条件返回0
        """
        # 检查杠杆是否超过限制
        if drift_user.get_leverage() > leverage * 10e3:
            return 0

        # 获取Binance可用余额
        balance_bn = float(um_futures_client.account()['availableBalance'])
        if balance_bn == 0:
            return 0

        # 获取Drift可用余额
        balance_drift = drift_user.get_free_collateral() / QUOTE_PRECISION
        send_msg(f'bn可活动余额{balance_bn}\ndrift可活动余额{balance_drift}')

        # 取两个平台较小的余额值，并留出3%的安全边际
        balance = min(balance_bn, balance_drift) * 0.97

        # 获取当前标记价格（取两个平台较高的价格作为保守估计）
        markPrice = max(float(um_futures_client.mark_price(symbol)['markPrice']),
                        drift_client.get_oracle_price_data_for_perp_market(
                            market_index=market_index).price / QUOTE_PRECISION)

        # 计算可开仓数量并按交易精度取整
        amount = str(balance * leverage / markPrice)
        amount_round = min(
            float(Decimal(amount).quantize(quantityPrecision, rounding=ROUND_DOWN)), size_max)

        # 检查最小交易量限制
        if amount_round < size_min:
            return 0

        # 计算名义价值
        notional = amount_round * markPrice

        # 检查最小交易额和开仓后的健康度
        if notional < 6 or calculate_health_drift(
                int(amount_round * BASE_PRECISION)) < health4open or calculate_health_bn(
            notional) < health4open:
            return 0

        return amount_round

    def open_bn_position(positionSide, amount):
        """
        在Binance合约市场开仓

        该函数在Binance上执行开仓操作，支持做多或做空。
        步骤：
        1. 设置合适的杠杆倍数
        2. 提交市价单开仓
        3. 发送开仓结果通知

        :param positionSide: 仓位方向，"LONG"或"SHORT"
        :param amount: 开仓数量
        :return: None，失败时抛出异常
        """
        try:
            # 设置杠杆倍数
            um_futures_client.change_leverage(symbol=symbol, leverage=leverage)

            # 提交市价单开仓
            tx = um_futures_client.new_order(
                symbol=symbol,
                side=open_map.get(positionSide),  # 根据仓位方向映射为买入或卖出
                type="MARKET",  # 市价单
                quantity=amount,
                positionSide=positionSide,  # 仓位方向
            )

            # 发送成功通知
            msg = f'bn开仓{symbol}成功，交易数量:{tx.get("origQty", 0)}'
            send_msg(msg)
        except:
            # 记录错误并通知
            traceback.print_exc()
            msg = f'bn开仓{symbol}失败'
            send_msg(msg)
            raise Exception(msg)  # 向上层抛出异常

    def close_bn_position(amount):
        """
        在Binance合约市场平仓或减仓

        该函数在Binance上执行平仓或减仓操作。特点：
        1. 循环重试，确保即使在网络不稳定时也能执行
        2. 如果失败会重新计算需要关闭的数量并再次尝试
        3. 默认关闭空头仓位（本程序中币安端始终做空）

        :param amount: 要平仓的数量
        :return: None
        """
        # 只要还有需要平仓的数量就继续尝试
        while amount:
            try:
                # 获取当前持仓信息
                position = um_futures_client.get_position_risk()
                if not position:  # 无持仓则退出
                    return

                # 本策略中币安端始终是做空
                positionSide = "SHORT"

                # 提交市价单平仓
                tx = um_futures_client.new_order(
                    symbol=symbol,
                    side=close_map.get(positionSide),  # 空头平仓需要买入
                    type="MARKET",  # 市价单
                    quantity=amount,
                    positionSide=positionSide,
                )

                # 发送成功通知
                msg = f'bn减仓{symbol}成功，交易数量:{tx.get("origQty", 0)}'
                send_msg(msg)
                break  # 成功执行后跳出循环
            except:
                # 失败后等待3秒再重试
                time.sleep(3)
                traceback.print_exc()
                msg = f'bn减仓{symbol}失败'
                send_msg(msg)
                # 重新计算平仓数量
                amount = get_amount_close().get('bn', 0)

    async def close_drift_position(amount):
        """
        在Drift协议平仓或减仓

        该函数在Drift上执行平仓或减仓操作。特点：
        1. 异步执行，支持循环重试
        2. 使用reduce_only参数确保只会减少现有仓位而不会反向开仓
        3. 默认平仓多头仓位（本程序中Drift端始终做多）

        :param amount: 要平仓的数量
        :return: None
        """
        # 只要还有需要平仓的数量就继续尝试
        while amount:
            try:
                # 创建市价单参数对象
                order_params = OrderParams(
                    market_type=MarketType.Perp(),  # 永续合约市场
                    order_type=OrderType.Market(),  # 市价单
                    market_index=market_index,  # 市场索引
                    base_asset_amount=int(amount * BASE_PRECISION),  # 数量（转换为内部精度）
                    direction=PositionDirection.Short(),  # 多头平仓需要做空操作
                    price=0,  # 市价单价格为0
                    reduce_only=True,  # 仅减仓，不会反向开仓
                )

                # 提交订单
                tx_sig = await drift_client.place_perp_order(order_params)

                # 发送成功通知
                msg = f"drift减仓{symbol}成功，交易数量:{amount}，交易签名:{tx_sig}"
                send_msg(msg)
                break  # 成功执行后跳出循环
            except:
                # 失败后等待3秒再重试
                await asyncio.sleep(3)
                traceback.print_exc()
                msg = f"drift减仓{symbol}失败"
                send_msg(msg)
                # 重新计算平仓数量
                amount = get_amount_close().get('drift', 0)

    async def open_drift_position(positionSide, amount):
        """
        在Drift协议开仓做多或做空

        该函数在Drift上执行开仓操作，支持做多或做空。
        步骤：
        1. 转换仓位方向为Drift API要求的格式
        2. 提交市价单开仓
        3. 发送开仓结果通知

        :param positionSide: 仓位方向，"LONG"或"SHORT"
        :param amount: 开仓数量
        :return: None，失败时抛出异常
        """
        try:
            # 转换仓位方向为Drift API格式
            if positionSide == "LONG":
                positionSide = PositionDirection.Long()
            else:
                positionSide = PositionDirection.Short()

            # 创建市价单参数对象
            order_params = OrderParams(
                market_type=MarketType.Perp(),  # 永续合约市场
                order_type=OrderType.Market(),  # 市价单
                direction=positionSide,  # 仓位方向
                market_index=market_index,  # 市场索引
                base_asset_amount=int(amount * BASE_PRECISION),  # 数量（转换为内部精度）
                price=0,  # 市价单价格为0
            )

            # 提交订单
            tx_sig = await drift_client.place_perp_order(order_params)

            # 发送成功通知
            msg = f"drift开仓{symbol}成功，交易数量:{amount}，交易签名:{tx_sig}"
            send_msg(msg)
        except:
            # 记录错误并通知
            traceback.print_exc()
            msg = f"drift开仓{symbol}失败"
            send_msg(msg)
            raise Exception(msg)  # 向上层抛出异常

    def drift_callback(event: WrappedEvent):
        """
        处理Drift协议事件回调，主要处理清算事件和资金费率更新事件

        该函数处理两种主要事件类型：
        1. LiquidationRecord: 当账户发生清算时，自动在币安端平仓相应数量以保持平衡
        2. FundingRateRecord: 当资金费率更新时，记录数据并在条件符合时执行套利策略

        :param event: Drift事件对象，包含事件类型和数据
        :return: None
        """
        print(datetime.now(), 'drift事件', event.event_type, '\n')

        # 处理清算事件 - 当Drift账户被清算时
        if event.event_type == "LiquidationRecord" and event.data.user == drift_user.user_public_key:
            send_msg(f'drift清算{symbol}')
            # 计算被清算的数量
            amount = float(Decimal(str(abs(event.data.liquidate_perp.base_asset_amount / BASE_PRECISION))).quantize(
                quantityPrecision, rounding=ROUND_DOWN))
            # 在币安端平掉相应数量以保持平衡
            close_bn_position(amount)
        # 处理资金费率更新事件
        elif event.event_type == "FundingRateRecord" and event.data.market_index == market_index:
            print(event)  # 打印完整事件信息用于调试
            # 获取资金费率数据
            funding_rate = event.data.funding_rate  # 原始资金费率值

            # 获取账户余额信息
            account_data = um_futures_client.account()
            # 总账户余额（可用保证金 + 已占用保证金）
            balance_bn_total = float(account_data['totalMarginBalance'])
            balance_drift_total = drift_user.get_total_collateral(margin_category=None) / QUOTE_PRECISION

            # 计算资金费率百分比（相对于标记价格）
            funding_rate_round = round(funding_rate / event.data.oracle_price_twap / 10,
                                       PERCENTAGE_PRECISION_EXP)

            # 获取对应的交易对符号
            symbol_funding = perp_market_indexes_symbol.get(event.data.market_index)

            # 构建记录数据
            excel_data_now = {
                '时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': symbol_funding,
                # 获取币安资金费率（如果是同一个交易对）
                'bn费率': float(um_futures_client.funding_rate(symbol, limit=1)[0]['fundingRate']) * 100 
                        if symbol_funding == symbol[:-4] else 0,
                'bn总额': balance_bn_total,
                'drift费率': funding_rate_round, 
                'drift总额': balance_drift_total,
                '双边总额': balance_bn_total + balance_drift_total  # 两个平台总资产
            }

            # 构建通知消息
            msg = f'==={symbol_funding}费率更新===\n' + '\n-------\n'.join(
                [f'{k}:{j}' for k, j in excel_data_now.items()])
            send_msg(msg)

            # 将数据保存到JSON文件
            with open('fundingRate.json', 'r+') as f:
                excel_data = json.load(f)
                excel_data.append(excel_data_now)
                f.seek(0)  # 重置文件指针位置
                f.truncate()  # 清空文件内容
                json.dump(excel_data, f, ensure_ascii=False)  # 写入新数据

            # 套利逻辑：仅在资金费率为负时执行（借贷方向对做空有利）
            if funding_rate >= 0:
                return  # 资金费率为正，不符合套利条件

            # 计算可开仓数量
            if (amount := get_amount_open()) == 0:
                send_msg(f'账户余额不足')
            # 如果是目标交易对且可开仓，执行套利策略：币安做空 + Drift做多
            elif symbol_funding == symbol[:-4]:
                open_bn_position("SHORT", amount)  # 币安做空
                asyncio.ensure_future(open_drift_position("LONG", amount), loop=loop)  # Drift做多

    event_subscriber.event_emitter.new_event += drift_callback

    def message_handler(_, message):
        print(datetime.now(), 'bn事件', message, '\n')
        send_msg(f'bn事件{message}')
        um_futures_client.renew_listen_key(listenKey=listenKey)
        print(datetime.now(), f'message renew listen key:{listenKey}')
        message = json.loads(message)
        if 'autoclose' in message.get('o', {}).get('c', '') and message.get('0', {}).get('x') == 'NEW':
            send_msg(f'bn清算{symbol}')
            amount = float(message.get('o', {}).get('q', get_amount_close().get('drift', 0)))
            asyncio.ensure_future(close_drift_position(amount), loop=loop)

    loop = asyncio.get_running_loop()

    def error_handler(_, message):
        while 1:
            try:
                print(datetime.now(), 'bn错误', message, '\n')
                my_client.socket_manager = my_client._initialize_socket(
                    stream_url="wss://fstream.binance.com/ws",
                    on_message=message_handler,
                    on_open=None,
                    on_close=None,
                    on_error=error_handler,
                    on_ping=None,
                    on_pong=None,
                    proxies=None,
                    logger=logging.getLogger(__name__)
                )
                # start the thread
                my_client.socket_manager.start()
                um_futures_client.renew_listen_key(listenKey=listenKey)
                my_client.user_data(listen_key=listenKey)
                print(datetime.now(), f'error renew listen key:{listenKey}')
                break
            except:
                time.sleep(5)
                continue

    my_client = UMFuturesWebsocketClient(on_message=message_handler, on_error=error_handler)
    my_client.user_data(listen_key=listenKey)

    def health():
        """
        定期检查两个平台的账户健康度并采取相应措施

        该函数根据账户健康度执行不同操作：
        1. 如果任一平台健康度低于关闭阈值，自动减仓并加快检查频率
        2. 如果任一平台健康度低于转移阈值，发出警告并增加检查频率
        3. 如果两个平台健康度都在安全范围内，维持正常检查频率

        :return: 包含健康度检查结果的消息字符串
        """
        global health_sleep
        try:
            # 获取两个平台的健康度
            health_drift = drift_user.get_health()
            health_bn = calculate_health_bn(0)

            # 情况1: 健康度过低，需要紧急减仓
            if health_drift < health4close or health_bn < health4close:
                # 计算需要平仓的数量
                amount = get_amount_close()
                # 同时在两个平台执行减仓
                asyncio.ensure_future(close_drift_position(amount.get('drift', 0)))
                close_bn_position(amount.get('bn', 0))
                # 加快检查频率为1分钟
                health_sleep = 60
                return f'drift定期检查，健康度{health_drift}\nbn定期检查，健康度{health_bn}\n正在减仓'

            # 情况2: 健康度较低，但尚未到紧急情况
            elif health_drift < health4transfer or health_bn < health4transfer:
                # 增加检查频率为2.5分钟
                health_sleep = 150
                return f'drift定期检查，健康度{health_drift}\nbn定期检查，健康度{health_bn}\n需要转移'

            # 情况3: 健康度良好
            health_sleep = 300  # 恢复正常检查频率为5分钟
            return f'drift定期检查，健康度{health_drift}\nbn定期检查，健康度{health_bn}\n仓位健康'
        except:
            # 检查失败
            return '健康度检查失败'

    # 主循环：定期健康检查和数据导出
    while 1:
        try:
            # 等待健康检查间隔时间
            await asyncio.sleep(health_sleep)

            # 执行健康度检查并发送结果
            msg_health = health()
            send_msg(msg_health)

            # 更新币安监听密钥（避免过期）
            um_futures_client.renew_listen_key(listenKey=listenKey)
            time_now = datetime.now()
            print(time_now, f'renew listen key:{listenKey}')

            # 每天晚上8点导出费率数据报表
            if time_now.hour == 20 and time_now.minute <= 5:
                with open('fundingRate.json', 'r+') as f:
                    excel_data = json.load(f)
                    if excel_data:  # 有数据才生成报表
                        # 将JSON数据转换为DataFrame
                        df = pd.DataFrame(excel_data)

                        # 将DataFrame转换为Excel内存文件
                        excel_buffer = BytesIO()
                        df.to_excel(excel_buffer, index=True)  # 包含索引列
                        excel_buffer.seek(0)  # 重置指针位置

                        # 准备上传文件
                        files = {
                            "media": (
                                f"费率{datetime.now().strftime('%Y%m%d')}.xlsx", excel_buffer,
                                "application/octet-stream")
                        }

                        # 第一步：上传媒体文件获取media_id
                        res = requests.post(
                            'https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key=ee6e64f7-4423-47d0-9f9c-583298d7ae02&type=file',
                            files=files)

                        # 第二步：发送文件消息
                        requests.post(
                            'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=ee6e64f7-4423-47d0-9f9c-583298d7ae02',
                            json={
                                "msgtype": "file",
                                "file": {
                                    "media_id": res.json().get('media_id')
                                }
                            })

                        # 清空数据准备收集下一天的数据
                        f.seek(0)
                        f.truncate()
                        json.dump([], f, ensure_ascii=False)
        except:
            # 出现异常时继续循环，确保程序不会终止
            continue

    # 下面的代码实际上永远不会执行，保持程序运行
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发


asyncio.run(main())
