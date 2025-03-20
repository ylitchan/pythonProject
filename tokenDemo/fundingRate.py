#!/usr/bin/env python

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
from driftpy.constants import BASE_PRECISION, PERCENTAGE_PRECISION_EXP, QUOTE_PRECISION, FUNDING_RATE_PRECISION
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
    symbol = 'SOLUSDT'
    market_index = 0
    leverage = 6
    size_min = 1
    size_max = 3
    health4open = 80
    health4close = 30
    health4transfer = 70
    positionClose = 4 / 8
    health_sleep = 300
    perp_market_indexes = {market_index, 2}
    spot_market_indexes = {0, }
    open_map = {"SHORT": "SELL", "LONG": "BUY"}
    close_map = {"SHORT": "BUY", "LONG": "SELL"}
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
        try:
            print(datetime.now(), msg)
            json_msg = {
                "msgtype": "text",
                "text": {'content': msg}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=ee6e64f7-4423-47d0-9f9c-583298d7ae02',
                json=json_msg)
        except:
            return

    def calculate_health_drift(base_asset_amount=0) -> int:
        if drift_user.is_being_liquidated():
            return 0
        total_collateral = drift_user.get_total_collateral(MarginCategory.MAINTENANCE)
        maintenance_margin_req = drift_user.get_margin_requirement(MarginCategory.MAINTENANCE)
        perp_position_cal = PerpPosition(
            last_cumulative_funding_rate=1063537496050, base_asset_amount=base_asset_amount,
            quote_asset_amount=-4829573078,
            quote_break_even_amount=-4801819309, quote_entry_amount=-4797405660, open_bids=0, open_asks=0,
            settled_pnl=94090387, lp_shares=0, last_base_asset_amount_per_lp=0, last_quote_asset_amount_per_lp=0,
            remainder_base_asset_amount=0, market_index=2, open_orders=0, per_lp_base=0
        )
        base_asset_value_cal = drift_user.calculate_weighted_perp_position_liability(
            perp_position=perp_position_cal,
            margin_category=MarginCategory.MAINTENANCE,
            liquidation_buffer=0,
            include_open_orders=False,
            strict=False,
        )
        maintenance_margin_req += base_asset_value_cal
        if maintenance_margin_req == 0 and total_collateral >= 0:
            return 100
        elif total_collateral <= 0:
            return 0
        else:
            return round(
                min(100, max(0, (1 - maintenance_margin_req / total_collateral) * 100))
            )

    def calculate_health_bn(notional) -> int:
        account_data = um_futures_client.account()
        # 总账户余额（可用保证金 + 已占用保证金）
        total_balance = float(account_data['totalMarginBalance'])
        position_data = um_futures_client.get_position_risk()
        total_maintenance_margin = 0.0
        for position in position_data:
            # 只考虑有持仓的头寸（positionAmt 不为 0）
            if float(position['positionAmt']) != 0:
                maintenance_margin = float(position['maintMargin'])  # 维持保证金
                total_maintenance_margin += maintenance_margin
        total_maintenance_margin += notional * 0.004
        if total_maintenance_margin == 0 and total_balance >= 0:
            return 100
        elif total_balance <= 0:
            return 0
        else:
            # 保证金比例 = 维持保证金 / 账户余额 × 100%
            return round(
                min(100, max(0, (1 - total_maintenance_margin / total_balance) * 100))
            )

    def get_amount_close():
        try:
            position = um_futures_client.get_position_risk()
            position = position[0]
            positionAmt = abs(float(position['positionAmt'])) * BASE_PRECISION
            perp_position = drift_user.get_perp_position(market_index)
            base_asset_amount = abs(perp_position.base_asset_amount)
            if base_asset_amount == positionAmt:
                amount = float(Decimal(positionAmt * positionClose / BASE_PRECISION).quantize(quantityPrecision,
                                                                                              rounding=ROUND_DOWN))
                return {'drift': amount, 'bn': amount}
            elif base_asset_amount > positionAmt:
                amount = float(Decimal((base_asset_amount - positionAmt) / BASE_PRECISION).quantize(quantityPrecision,
                                                                                                    rounding=ROUND_DOWN))
                return {'drift': amount, 'bn': 0}
            else:
                amount = float(Decimal((positionAmt - base_asset_amount) / BASE_PRECISION).quantize(quantityPrecision,
                                                                                                    rounding=ROUND_DOWN))
                return {'drift': 0, 'bn': amount}
        except:
            return {'drift': 0, 'bn': 0}

    def get_amount_open():
        if drift_user.get_leverage() > leverage * 10e3:
            return 0
        balance_bn = float(um_futures_client.account()['availableBalance'])
        if balance_bn == 0:
            return 0
        balance_drift = drift_user.get_free_collateral() / QUOTE_PRECISION
        send_msg(f'bn可活动余额{balance_bn}\ndrift可活动余额{balance_drift}')
        balance = min(balance_bn, balance_drift) * 0.97
        markPrice = max(float(um_futures_client.mark_price(symbol)['markPrice']),
                        drift_client.get_oracle_price_data_for_perp_market(
                            market_index=market_index).price / QUOTE_PRECISION)
        amount = str(balance * leverage / markPrice)
        amount_round = min(
            float(Decimal(amount).quantize(quantityPrecision, rounding=ROUND_DOWN)), size_max)
        if amount_round < size_min:
            return 0
        notional = amount_round * markPrice
        if notional < 6 or calculate_health_drift(
                int(amount_round * BASE_PRECISION)) < health4open or calculate_health_bn(
            notional) < health4open:
            return 0
        return amount_round

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
            traceback.print_exc()
            msg = f'bn开仓{symbol}失败'
            send_msg(msg)
            raise Exception(msg)

    def close_bn_position(amount):
        while amount:
            try:
                position = um_futures_client.get_position_risk()
                if not position:
                    return
                positionSide = "SHORT"
                tx = um_futures_client.new_order(
                    symbol=symbol,
                    side=close_map.get(positionSide),
                    type="MARKET",
                    quantity=amount,
                    positionSide=positionSide,
                )
                msg = f'bn减仓{symbol}成功，交易数量:{tx.get("origQty", 0)}'
                send_msg(msg)
                break
            except:
                time.sleep(3)
                traceback.print_exc()
                msg = f'bn减仓{symbol}失败'
                send_msg(msg)
                amount = get_amount_close().get('bn', 0)

    async def close_drift_position(amount):
        while amount:
            try:
                order_params = OrderParams(
                    market_type=MarketType.Perp(),
                    order_type=OrderType.Market(),
                    market_index=market_index,
                    base_asset_amount=amount * BASE_PRECISION,
                    direction=PositionDirection.Short(),
                    price=0,
                    reduce_only=True,
                )
                tx_sig = await drift_client.place_perp_order(order_params)
                msg = f"drift减仓{symbol}成功，交易数量:{amount}，交易签名:{tx_sig}"
                send_msg(msg)
                break
            except:
                await asyncio.sleep(3)
                traceback.print_exc()
                msg = f"drift减仓{symbol}失败"
                send_msg(msg)
                amount = get_amount_close().get('drift', 0)

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
            traceback.print_exc()
            msg = f"drift开仓{symbol}失败"
            send_msg(msg)
            raise Exception(msg)

    def drift_callback(event: WrappedEvent):
        """处理清算事件"""
        print(datetime.now(), 'drift事件', event.event_type, '\n')
        if event.event_type == "LiquidationRecord" and event.data.user == drift_user.user_public_key:
            send_msg(f'drift清算{symbol}')
            amount = get_amount_close()
            close_bn_position(amount)
        elif event.event_type == "FundingRateRecord" and event.data.market_index == market_index:
            funding_rate = event.data.funding_rate
            account_data = um_futures_client.account()
            # 总账户余额（可用保证金 + 已占用保证金）
            balance_bn_total = float(account_data['totalMarginBalance'])
            balance_drift_total = drift_user.get_total_collateral(margin_category=None) / QUOTE_PRECISION
            funding_rate_round = round(funding_rate / event.data.oracle_price_twap / FUNDING_RATE_PRECISION * 1e2,
                                       PERCENTAGE_PRECISION_EXP)
            symbol_funding = perp_market_indexes_symbol.get(event.data.market_index)
            excel_data_now = {'时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                              'symbol': symbol_funding,
                              'bn费率': float(um_futures_client.funding_rate(symbol, limit=1)[0][
                                                  'fundingRate']) * 100 if symbol_funding == symbol[:-4] else 0,
                              'bn总额': balance_bn_total,
                              'drift费率': funding_rate_round, 'drift总额': balance_drift_total,
                              '双边总额': balance_bn_total + balance_drift_total}
            msg = f'==={symbol_funding}费率更新===\n' + '\n-------\n'.join(
                [f'{k}:{j}' for k, j in excel_data_now.items()])
            send_msg(msg)
            with open('fundingRate.json', 'r+') as f:
                excel_data = json.load(f)
                excel_data.append(excel_data_now)
                f.seek(0)
                f.truncate()
                json.dump(excel_data, f, ensure_ascii=False)
            if (amount := get_amount_open()) == 0:
                send_msg(f'账户余额不足')
            elif symbol_funding == symbol[:-4] and funding_rate < 0:
                open_bn_position("SHORT", amount)
                asyncio.ensure_future(open_drift_position("LONG", amount), loop=loop)

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
        global health_sleep
        try:
            health_drift = drift_user.get_health()
            health_bn = calculate_health_bn(0)
            if health_drift < health4close or health_bn < health4close:
                amount = get_amount_close()
                asyncio.ensure_future(close_drift_position(amount.get('drift', 0)))
                close_bn_position(amount.get('bn', 0))
                health_sleep = 60
                return f'drift定期检查，健康度{health_drift}\nbn定期检查，健康度{health_bn}\n正在减仓'
            elif health_drift < health4transfer or health_bn < health4transfer:
                health_sleep = 150
                return f'drift定期检查，健康度{health_drift}\nbn定期检查，健康度{health_bn}\n需要转移'
            health_sleep = 300
            return f'drift定期检查，健康度{health_drift}\nbn定期检查，健康度{health_bn}\n仓位健康'
        except:
            return '健康度检查失败'

    while 1:
        try:
            await asyncio.sleep(health_sleep)
            msg_health = health()
            send_msg(msg_health)
            um_futures_client.renew_listen_key(listenKey=listenKey)
            time_now = datetime.now()
            print(time_now, f'renew listen key:{listenKey}')
            if time_now.hour == 20 and time_now.minute <= 5:
                with open('fundingRate.json', 'r+') as f:
                    excel_data = json.load(f)
                    if excel_data:
                        df = pd.DataFrame(excel_data)
                        # 将DataFrame转换为CSV内存文件
                        excel_buffer = BytesIO()
                        df.to_excel(excel_buffer, index=True)  # utf-8-sig解决中文乱码
                        excel_buffer.seek(0)  # 重置指针位置
                        files = {
                            "media": (
                                f"费率{datetime.now().strftime('%Y%m%d')}.xlsx", excel_buffer,
                                "application/octet-stream")
                        }
                        res = requests.post(
                            'https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key=ee6e64f7-4423-47d0-9f9c-583298d7ae02&type=file',
                            files=files)
                        requests.post(
                            'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=ee6e64f7-4423-47d0-9f9c-583298d7ae02',
                            json={
                                "msgtype": "file",
                                "file": {
                                    "media_id": res.json().get('media_id')
                                }
                            })
                        f.seek(0)
                        f.truncate()
                        json.dump([], f, ensure_ascii=False)
        except:
            continue
    stop_event = asyncio.Event()
    await stop_event.wait()  # 等待事件触发


asyncio.run(main())
