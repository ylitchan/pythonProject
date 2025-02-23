#!/usr/bin/env python

import asyncio
import json
import logging
from datetime import datetime

from anchorpy import Wallet
from binance.lib.utils import config_logging
from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient
from driftpy.constants import BASE_PRECISION
from driftpy.drift_client import DriftClient
from driftpy.events.event_subscriber import EventSubscriber
from driftpy.events.types import EventSubscriptionOptions, WebsocketLogProviderConfig
from driftpy.events.types import WrappedEvent
from driftpy.types import OrderParams, OrderType
from driftpy.types import PositionDirection
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair


async def main():
    open_map = {"SHORT": "SELL", "LONG": "BUY"}
    close_map = {"SHORT": "BUY", "LONG": "SELL"}
    config_logging(logging, logging.INFO)
    with open(r'D:\PycharmProjects\pythonProject\tokenDemo\bn.json', 'r') as f:
        bn_api = json.load(f)
    client = UMFutures(bn_api.get('api_key'))
    listenKey = client.new_listen_key()["listenKey"]
    logging.info("Listen key : {}".format(listenKey))
    um_futures_client = UMFutures(key=bn_api.get('api_key'), secret=bn_api.get('api_secret'))
    sp = {i['symbol']: i['quantityPrecision'] for i in um_futures_client.exchange_info()['symbols']}
    url = 'https://mainnet.helius-rpc.com/?api-key=346cd7c9-73a9-4916-a150-4157181b99dc'  # replace w/ any rpc
    connection = AsyncClient(url)
    with open('PRIVATE_KEY', 'r') as f:
        PRIVATE_KEY = f.read()
    wallet = Wallet(Keypair.from_base58_string(PRIVATE_KEY))
    # wallet= Wallet(Keypair.from_base58_string('26JUu5XCsF3iSrFaWfr8FDh9gRVgWb6AYCaTtPbzVxhrT8RRZRb4bcC45ZTuaynwCfQzR9FMxo9rNvrYbZZXsA3Y'))
    drift_client = DriftClient(connection, wallet, "mainnet", perp_market_indexes=[2], spot_market_indexes=[0])
    # 4. 订阅账户数据
    await drift_client.unsubscribe()
    await drift_client.subscribe()
    # 获取当前用户账户
    drift_user = drift_client.get_user()
    account_subscriber = drift_client.account_subscriber
    for market_index in {i.market_index for i in drift_user.get_user_account().spot_positions}:
        await account_subscriber.subscribe_to_perp_market(market_index)
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

    def get_amount():
        balance_bn = {i['asset']: float(i['balance']) for i in um_futures_client.balance()}.get('USDT', 0)
        balance_drift = drift_user.get_free_collateral() / 10e5
        balance = max(min(balance_bn, balance_drift), 6)
        markPrice = max(float(um_futures_client.mark_price('ETHUSDT')['markPrice']),
                        drift_client.get_oracle_price_data_for_perp_market(
                            market_index=2).price)
        amount = round(balance / markPrice, sp.get('ETHUSDT'))
        return amount * 5

    def open_bn_position(positionSide, amount):
        um_futures_client.change_leverage(symbol='ETHUSDT', leverage=5)
        response = um_futures_client.new_order(
            symbol="ETHUSDT",
            side=open_map.get(positionSide),
            type="MARKET",
            quantity=amount,
            positionSide=positionSide,
        )
        logging.info(f'币安开仓成功，{response}')

    def close_bn_position():
        position = um_futures_client.get_position_risk()[0]
        positionSide = position['positionSide']
        positionAmt = position['positionAmt']
        response = um_futures_client.new_order(
            symbol="USDCUSDT",
            side=close_map.get(positionSide),
            type="MARKET",
            quantity=abs(float(positionAmt)),
            positionSide=positionSide,
        )
        logging.info(f'币安平仓成功，{response}')

    async def close_drift_position(base_asset_amount):
        order_params = OrderParams(
            order_type=OrderType.Market(),
            market_index=2,
            base_asset_amount=abs(base_asset_amount),
            direction=(
                PositionDirection.Long()
                if base_asset_amount < 0
                else PositionDirection.Short()
            ),
            price=0,
            reduce_only=True,
        )
        tx_sig = await drift_client.place_perp_order(order_params)
        print(f"drift平仓成功，交易签名: {tx_sig}")

    async def open_drift_position(positionSide, amount):
        if positionSide == "LONG":
            positionSide = PositionDirection.Long()
        else:
            positionSide = PositionDirection.Short()
        order_params = OrderParams(
            order_type=OrderType.Market(),
            direction=positionSide,
            market_index=2,
            base_asset_amount=int(amount * BASE_PRECISION),
            price=0,
        )
        tx_sig = await drift_client.place_perp_order(order_params)
        print(f"drift开仓成功，交易签名: {tx_sig}")

    def drift_callback(event: WrappedEvent):
        """处理清算事件"""
        print(datetime.now(), event, '\n')
        if event.event_type == "LiquidationRecord" and event.data.user == drift_user.user_public_key:
            close_bn_position()
        elif event.event_type == "FundingRateRecord":
            positions = drift_user.get_perp_position(2)
            funding_rate = event.data.funding_rate
            if positions and funding_rate * positions.base_asset_amount < 0:
                return
            elif positions and positions.base_asset_amount:
                asyncio.run(close_drift_position(positions.base_asset_amount))
                close_bn_position()
            amount = get_amount()
            if funding_rate > 0:
                open_bn_position("LONG", amount)
                asyncio.ensure_future(open_drift_position("SHORT", amount), loop=loop)
            elif funding_rate < 0:
                open_bn_position("SHORT", amount)
                asyncio.ensure_future(open_drift_position("LONG", amount), loop=loop)
        # 检查是否是自己的账户被清算
        # if event.data.user == user_public_key:
        #     print(f"我的仓位被强平！清算详情: {event.data}")
        #     # 提取更多信息，例如清算的市场和数量
        #     market_index = event.data.market_index
        #     liquidated_amount = event.data.base_asset_amount / 1e9  # 转换为可读单位
        #     print(f"市场索引: {market_index}, 清算数量: {liquidated_amount}")

    event_subscriber.event_emitter.new_event += drift_callback

    def message_handler(_, message):
        print(datetime.now(), message, '\n')
        message = json.loads(message)
        # asyncio.ensure_future(open_drift_position('LONG', 0.001), loop=loop)
        if 'autoclose' in message.get('o', {}).get('c', ''):
            base_asset_amount = drift_user.get_perp_position(2).base_asset_amount
            asyncio.ensure_future(close_drift_position(base_asset_amount), loop=loop)

    loop = asyncio.get_running_loop()
    my_client = UMFuturesWebsocketClient(on_message=message_handler)
    my_client.user_data(listen_key=listenKey)
    while 1:
        await asyncio.sleep(1)
        # client.renew_listen_key(listenKey=listenKey)
    my_client.stop()
    logging.debug("closing ws connection")


asyncio.run(main())
