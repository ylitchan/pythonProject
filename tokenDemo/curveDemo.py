import asyncio
import traceback
from datetime import datetime

import requests

session = requests.Session()
session.headers = {'Content-Type': 'application/json'}


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


def get_close():
    current_time = int(datetime.now().timestamp())
    response = requests.get("https://prices.curve.fi/v1/ohlc/ethereum/0x2673099769201c08E9A5e63b25FBaF25541A6557",
                            params={
                                'main_token': "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                                'reference_token': "0xdf3ac4F479375802A821f7b7b46Cd7EB5E4262cC",
                                'agg_number': "15",
                                'agg_units': "minute",
                                'start': current_time - 15 * 60,
                                'end': current_time
                            })
    price_close = response.json()['data'][-1]['close']
    response2 = requests.get("https://prices.curve.fi/v1/ohlc/ethereum/0x880F2fB3704f1875361DE6ee59629c6c6497a5E3",
                             params={
                                 'main_token': "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                                 'reference_token': "0x97de57eC338AB5d51557DA3434828C5DbFaDA371",
                                 'agg_number': "15",
                                 'agg_units': "minute",
                                 'start': current_time - 15 * 60,
                                 'end': current_time
                             })
    price_close2 = response2.json()['data'][-1]['close']
    send_msg(f'eUSD/USDC价格:\n{price_close}\neUSD V1/USDC价格:\n{price_close2}')


async def main():
    while True:
        try:
            get_close()
        except:
            traceback.print_exc()
        await asyncio.sleep(3600)


asyncio.run(main())
