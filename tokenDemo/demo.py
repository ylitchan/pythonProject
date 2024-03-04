import aiohttp
import asyncio
remote='wss://zws5.web.telegram.org/apiws'
headers={'Sec-WebSocket-Protocol': 'binary','Sec-WebSocket-Key': 'C9ZQyvGZrsYFjdUMvaFCVg==','Sec-WebSocket-Version': '13','Upgrade': 'websocket'}
async def startup():


    async with aiohttp.ClientSession().ws_connect(url=remote, proxy='http://127.0.0.1:10810',headers=headers) as aws:#这里走代理
        # await aws.send_json(json)
        while 1:
            print('-----------------------------------')
            a={
                "type": "Buffer",
                "data": [
                    164,
                    10,
                    197,
                    208,
                    39,
                    193,
                    73,
                    196,
                    209,
                    42,
                    18,
                    185,
                    214,
                    227,
                    123,
                    22,
                    31,
                    142,
                    67,
                    171,
                    235,
                    176,
                    66,
                    226,
                    221,
                    66,
                    61,
                    232,
                    53,
                    75,
                    125,
                    171,
                    157,
                    7,
                    228,
                    154,
                    17,
                    253,
                    60,
                    234,
                    107,
                    33,
                    165,
                    52,
                    234,
                    154,
                    194,
                    118,
                    20,
                    204,
                    185,
                    38,
                    205,
                    206,
                    129,
                    216,
                    31,
                    188,
                    4,
                    75,
                    122,
                    81,
                    9,
                    53
                ]
            }
            await aws.send_json(a)
            print('============')
            recv_text = await aws.receive()
            print(recv_text)
            # price=recv_text.get('payload',{}).get('data',{}).get('onUpdatePrice',{}).get('priceUsd',0)
            # if price >= high_prices[0]:
            #     high_prices.pop(0)
            #     await push('币价提醒',price)
            # elif price <= low_prices[0]:
            #     low_prices.pop(0)
            #     await push('币价提醒',price)



if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(startup())
    except Exception as e:
        print('退出', e)