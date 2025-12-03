#!/usr/bin/env python
import json
import logging

from binance.error import ClientError
from binance.lib.utils import config_logging
from binance.um_futures import UMFutures

config_logging(logging, logging.DEBUG)
with open(r'D:\PycharmProjects\pythonProject\tokenDemo\bn.json', 'r') as f:
    bn_api = json.load(f)
key = bn_api.get('api_key')
secret = bn_api.get('api_secret')

um_futures_client = UMFutures(key=key, secret=secret)
a=um_futures_client.exchange_info()
b=um_futures_client.change_leverage('USDCUSDT', 1)
try:
    response = um_futures_client.new_order(
        symbol="USDCUSDT",
        side="BUY",
        type="MARKET",
        quantity=round(6.22,0),
        # timeInForce="GTC",
        # price=59808.02,
    )
    logging.info(response)
except ClientError as error:
    logging.error(
        "Found error. status: {}, error code: {}, error message: {}".format(
            error.status_code, error.error_code, error.error_message
        )
    )
