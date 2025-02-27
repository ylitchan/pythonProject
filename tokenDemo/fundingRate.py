#!/usr/bin/env python

import asyncio
import json
import logging
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

import requests
from anchorpy import Wallet
from binance.lib.utils import config_logging
from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient
from driftpy.constants import BASE_PRECISION
from driftpy.drift_client import DriftClient
from driftpy.events.event_subscriber import EventSubscriber
from driftpy.events.types import EventSubscriptionOptions, WebsocketLogProviderConfig
from driftpy.events.types import WrappedEvent
from driftpy.types import OrderParams, OrderType, MarketType
from driftpy.types import PositionDirection
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair


async def main():
    symbol = 'ETHUSDT'
    market_index = 2
    leverage = 20
    open_map = {"SHORT": "SELL", "LONG": "BUY"}
    close_map = {"SHORT": "BUY", "LONG": "SELL"}
    config_logging(logging, logging.INFO)
    with open(r'bn.json', 'r') as f:
        bn_api = json.load(f)
    session = requests.Session()
    session.headers = {'Content-Type': 'application/json'}
    um_futures_client = UMFutures(key=bn_api.get('api_key'), secret=bn_api.get('api_secret'))
    listenKey = um_futures_client.new_listen_key()["listenKey"]
    logging.info("Listen key : {}".format(listenKey))
    sp = {i['symbol']: i['quantityPrecision'] for i in um_futures_client.exchange_info()['symbols']}
    url = 'https://mainnet.helius-rpc.com/?api-key=346cd7c9-73a9-4916-a150-4157181b99dc'  # replace w/ any rpc
    connection = AsyncClient(url)
    with open('PRIVATE_KEY', 'r') as f:
        PRIVATE_KEY = f.read()
    wallet = Wallet(Keypair.from_base58_string(PRIVATE_KEY))
    # wallet= Wallet(Keypair.from_base58_string('26JUu5XCsF3iSrFaWfr8FDh9gRVgWb6AYCaTtPbzVxhrT8RRZRb4bcC45ZTuaynwCfQzR9FMxo9rNvrYbZZXsA3Y'))
    drift_client = DriftClient(connection, wallet, "mainnet", perp_market_indexes=[0, market_index],
                               spot_market_indexes=[0])
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

    def send_msg(msg):
        print(msg)
        json_msg = {
            "msgtype": "text",
            "text": {'content': msg}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=ee6e64f7-4423-47d0-9f9c-583298d7ae02',
            json=json_msg)

    def get_amount():
        quantityPrecision = sp.get(symbol)
        balance_bn = {i['asset']: float(i['balance']) for i in um_futures_client.balance()}.get('USDT', 0)
        balance_drift = drift_user.get_free_collateral() / 10e5
        send_msg(f'bn余额{balance_bn}\ndrift余额{balance_drift}')
        balance = min(balance_bn, balance_drift)
        if balance < 6:
            amout_round = 0
        else:
            markPrice = max(float(um_futures_client.mark_price(symbol)['markPrice']),
                            drift_client.get_oracle_price_data_for_perp_market(
                                market_index=market_index).price / 10e5)
            amout = str(balance / markPrice)
            amout_round = float(Decimal(amout).quantize(Decimal(f'0.{"1" * quantityPrecision}'), rounding=ROUND_DOWN))
        if amout_round == 0:
            send_msg('账户余额不足')
        return amout_round * leverage

    def open_bn_position(positionSide, amount):
        try:
            um_futures_client.change_leverage(symbol=symbol, leverage=leverage)
            tx = um_futures_client.new_order(
                symbol=symbol,
                side=open_map.get(positionSide),
                type="MARKET",
                quantity=amount,
                positionSide=positionSide,
            )
            msg = f'bn开仓{symbol}成功，交易数量:{tx.get("origQty", 0)}'
            send_msg(msg)
        except:
            msg = f'bn开仓{symbol}失败'
            send_msg(msg)
            raise Exception(msg)

    def close_bn_position():
        try:
            position = um_futures_client.get_position_risk()[0]
            positionSide = position['positionSide']
            positionAmt = position['positionAmt']
            tx = um_futures_client.new_order(
                symbol=symbol,
                side=close_map.get(positionSide),
                type="MARKET",
                quantity=abs(float(positionAmt)),
                positionSide=positionSide,
            )
            msg = f'bn平仓{symbol}成功，交易数量:{tx.get("origQty", 0)}'
            send_msg(msg)
        except:
            msg = f'bn平仓{symbol}失败'
            send_msg(msg)
            raise Exception(msg)

    async def close_drift_position(base_asset_amount):
        try:
            order_params = OrderParams(
                market_type=MarketType.Perp(),
                order_type=OrderType.Market(),
                market_index=market_index,
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
            msg = f"drift平仓{symbol}成功，交易数量:{base_asset_amount}，交易签名:{tx_sig}"
            send_msg(msg)
        except:
            msg = f"drift平仓{symbol}失败"
            send_msg(msg)
            raise Exception(msg)

    async def open_drift_position(positionSide, amount):
        try:
            if positionSide == "LONG":
                positionSide = PositionDirection.Long()
            else:
                positionSide = PositionDirection.Short()
            order_params = OrderParams(
                market_type=MarketType.Perp(),
                order_type=OrderType.Market(),
                direction=positionSide,
                market_index=market_index,
                base_asset_amount=int(amount * BASE_PRECISION),
                price=0,
            )
            tx_sig = await drift_client.place_perp_order(order_params)
            msg = f"drift开仓{symbol}成功，交易数量:{amount}，交易签名:{tx_sig}"
            send_msg(msg)
        except:
            msg = f"drift开仓{symbol}失败"
            send_msg(msg)
            raise Exception(msg)

    def drift_callback(event: WrappedEvent):
        """处理清算事件"""
        print(datetime.now(), 'drift事件', event.event_type, '\n')
        if event.event_type == "LiquidationRecord" and event.data.user == drift_user.user_public_key:
            send_msg(f'drift清算{symbol}')
            try:
                close_bn_position()
            except:
                send_msg(f'{symbol}平对手仓bn失败')
        elif event.event_type == "FundingRateRecord" and event.data.market_index == market_index:
            funding_rate = event.data.funding_rate
            send_msg(f'{symbol}费率更新:{funding_rate}')
            positions = drift_user.get_perp_position(market_index)
            if positions and funding_rate * positions.base_asset_amount < 0:
                return
            elif positions and positions.base_asset_amount:
                close_bn_position()
                asyncio.run_coroutine_threadsafe(close_drift_position(positions.base_asset_amount), loop).result()
            amount = get_amount()
            if amount == 0:
                return
            if funding_rate > 0:
                open_bn_position("LONG", amount)
                asyncio.run_coroutine_threadsafe(open_drift_position("SHORT", amount), loop).result()
            elif funding_rate < 0:
                open_bn_position("SHORT", amount)
                asyncio.run_coroutine_threadsafe(open_drift_position("LONG", amount), loop).result()

    event_subscriber.event_emitter.new_event += drift_callback

    def message_handler(_, message):
        print(datetime.now(), 'bn事件', message, '\n')
        send_msg(f'bn事件{message}')
        um_futures_client.renew_listen_key(listenKey=listenKey)
        print(datetime.now(), f'renew listen key:{listenKey}')
        message = json.loads(message)
        if 'autoclose' in message.get('o', {}).get('c', '') and message.get('0', {}).get('x') == 'NEW':
            send_msg(f'bn清算{symbol}')
            try:
                base_asset_amount = drift_user.get_perp_position(market_index).base_asset_amount
                asyncio.run_coroutine_threadsafe(close_drift_position(base_asset_amount), loop).result()
            except:
                send_msg(f'{symbol}平对手仓drift失败')

    loop = asyncio.get_running_loop()

    def error_handler(_, message):
        print(datetime.now(), 'bn错误', message, '\n')
        send_msg(f'bn错误{message}')
        my_client.socket_manager = my_client._initialize_socket(
            stream_url="wss://fstream.binance.com",
            on_message=None,
            on_open=None,
            on_close=None,
            on_error=None,
            on_ping=None,
            on_pong=None,
            proxies=None,
        )
        # start the thread
        my_client.socket_manager.start()
        um_futures_client.renew_listen_key(listenKey=listenKey)
        my_client.user_data(listen_key=listenKey)
        send_msg(f'bn重连成功')
        print(datetime.now(), f'renew listen key:{listenKey}')

    def open_handler(_):
        print(datetime.now(), 'bn连接', '\n')
        send_msg('bn连接成功')
        um_futures_client.renew_listen_key(listenKey=listenKey)
        print(datetime.now(), f'renew listen key:{listenKey}')

    my_client = UMFuturesWebsocketClient(on_message=message_handler, on_error=error_handler, on_open=open_handler)
    my_client.user_data(listen_key=listenKey)
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发


asyncio.run(main())
