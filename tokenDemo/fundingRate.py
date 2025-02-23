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
from driftpy.constants.perp_markets import devnet_perp_market_configs
from driftpy.drift_client import DriftClient
from driftpy.events.event_subscriber import EventSubscriber
from driftpy.events.types import EventSubscriptionOptions, WebsocketLogProviderConfig
from driftpy.events.types import WrappedEvent
from driftpy.types import PositionDirection
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair


async def main():
    open_map = {"SHORT": "SELL", "LONG": "BUY"}
    close_map = {"SHORT": "BUY", "LONG": "SELL"}
    config_logging(logging, logging.DEBUG)
    with open(r'D:\PycharmProjects\pythonProject\tokenDemo\bn.json', 'r') as f:
        bn_api = json.load(f)
    client = UMFutures(bn_api.get('api_key'))
    response = client.new_listen_key()
    logging.info("Listen key : {}".format(response["listenKey"]))
    um_futures_client = UMFutures(key=bn_api.get('api_key'), secret=bn_api.get('api_secret'))
    sp = {i['symbol']: i['quantityPrecision'] for i in um_futures_client.exchange_info()['symbols']}
    url = 'https://api.mainnet-beta.solana.com'  # replace w/ any rpc
    connection = AsyncClient(url)
    perp_market_indexes = [i.market_index for i in devnet_perp_market_configs]
    with open('PRIVATE_KEY', 'r') as f:
        PRIVATE_KEY = f.read()
    wallet = Wallet(Keypair.from_base58_string(PRIVATE_KEY))
    # wallet= Wallet(Keypair.from_base58_string('26JUu5XCsF3iSrFaWfr8FDh9gRVgWb6AYCaTtPbzVxhrT8RRZRb4bcC45ZTuaynwCfQzR9FMxo9rNvrYbZZXsA3Y'))
    drift_client = DriftClient(connection, wallet, "mainnet", perp_market_indexes=[2])
    # 4. 订阅账户数据
    await drift_client.unsubscribe()
    await drift_client.subscribe()
    # 获取当前用户账户
    drift_user = drift_client.get_user()
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
        balance = {i['asset']: float(i['balance']) for i in um_futures_client.balance()}
        amount_bn = round(balance.get('USDT', 0) / float(um_futures_client.mark_price('ETHUSDT')['markPrice']),
                          sp.get('ETHUSDT'))
        return amount_bn * 5
        amount_drift = round(
            drift_user.get_user_account().total_deposits / drift_client.get_oracle_price_data_for_perp_market(
                market_index=2).price, sp.get('ETHUSDT'))
        return min(amount_bn, amount_drift)

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

    async def close_drift_position():
        tx_sig = await drift_client.close_position(market_index=2)
        print(f"drift平仓成功，交易签名: {tx_sig}")

    async def open_drift_position(positionSide, amount):
        if positionSide == "LONG":
            positionSide = PositionDirection.Long()
        else:
            positionSide = PositionDirection.Short()
        tx_sig = await drift_client.open_position(
            direction=positionSide,
            amount=int(amount * BASE_PRECISION),
            market_index=2,
        )
        print(f"drift开仓成功，交易签名: {tx_sig}")

    def drift_callback(event: WrappedEvent):
        """处理清算事件"""
        print(datetime.now(), event, '\n')
        if event.event_type == "LiquidationRecord" and event.data.user == drift_user.user_public_key:
            close_bn_position()
        elif event.event_type == "FundingRateRecord":
            positions = drift_user.get_user_position(2)
            funding_rate = event.data.funding_rate
            if positions and funding_rate * positions.base_asset_amount < 0:
                return
            elif positions:
                asyncio.run(close_drift_position())
                close_bn_position()
            amount = get_amount()
            if funding_rate > 0:
                open_bn_position("SHORT", amount)
                open_drift_position("SHORT", amount)
            elif funding_rate < 0:
                open_bn_position("LONG", amount)
                open_drift_position("LONG", amount)
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
        if 'autoclose' in message.get('o',{}).get('c',''):
            asyncio.run(close_drift_position())

    my_client = UMFuturesWebsocketClient(on_message=message_handler)
    my_client.user_data(listen_key=response["listenKey"])
    while 1:
        continue
        await asyncio.sleep(60)
    my_client.stop()
    logging.debug("closing ws connection")


asyncio.run(main())
