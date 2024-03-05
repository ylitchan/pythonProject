import asyncio
import datetime
import re
import time
import aiohttp
import asyncio
import requests
# while 1:
#     resp=requests.post('https://bitkeep.com/marketApi/quotev2/getTokenMarket',json={"chain":"arbitrum","contract":"0x463913d3a3d3d291667d53b8325c598eb88d3b0e"})
#     print(resp.json()['data']['price'])
#     time.sleep(2)
# headers={"user-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.41","cookie":"cf_clearance=AZeCWKZ4AcZ4k4G7m0_jwqZ0vwTqg7s8bW1IHHLt9m8-1676532903-0-160; chakra-ui-color-mode=dark; _ga=GA1.1.1029131385.1676532909; alertsMigration=1.0.0; watchlistInitialStateMigration=1.0.0; globalChartSettingsMigration=1.0.0; pairChartSettingsMigration=1.0.0; studyTemplatesMigration=1.0.0; watchlistsMigration=1.0.0; __cf_bm=thag8DXkDe0gdqct9ytTFcK37V4RYbRCaPCk1CzE5Zs-1676535399-0-AYpa9LVelLeWmcH0B4O+s+egpdiKcQiGcbak8rKDQLm13ckt7zdFPzpv/5/XdBSWA1IwY5VDceETihfOXOEPju0O/KupHlp+FTesrqUWWtN9; _ga_532KFVB4WT=GS1.1.1676532909.1.1.1676536662.60.0.0"}
# a=requests.post("https://dexscreener.com/arbitrum/0x751f3b8ca139bc1f3482b193297485f14208826a",headers=headers)
# print(a.text)
# from pyquery import PyQuery as pq
# def push(title, content):
#     json = {
#         "token": "e73179f25ade41729eae654a2decec15",
#         "title": title,
#         "content": content,
#         "topic": "1",
#         "template": "html"
#     }
#     requests.post(url='http://www.pushplus.plus/send/', json=json)
# while 1:
#     doc = pq(url='https://dexscreener.com/arbitrum/0x751f3b8ca139bc1f3482b193297485f14208826a',headers=headers)
#     price=float(re.search(r'\$.*? ',doc('title').text()).group().replace('$',''))
#     print(datetime.datetime.now(),price,price-0.1830,(price-0.1830)/0.001830)
#     if price>=0.2730:
#         push('sliz',price)
#         break
#     time.sleep(60)

# print(price=int(re.search(r'\$.*? ',doc('title').text()).group()))
# print("==================")
# headers={"Content-Type": "application/json","x-api-key":"042J22trve3hqIDndKqxR7Y9vyCc9gQL8CP29lXz","user-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.50"}1.71732
# json={"query":"query ExampleQuery {\n  getNetworks {\n    name\n  }\n}\n","variables":{},"operationName":"ExampleQuery"}
# res=requests.post('https://api.defined.fi/',headers=headers,json=json)
# print(res.json())
remote='wss://realtime.api.defined.fi/graphql/realtime?header=eyJob3N0IjogInJlYWx0aW1lLmFwaS5kZWZpbmVkLmZpIiwgIkF1dGhvcml6YXRpb24iOiAiMDQySjIydHJ2ZTNocUlEbmRLcXhSN1k5dnlDYzlnUUw4Q1AyOWxYeiIgfQ==&payload=e30='
headers={'Sec-WebSocket-Protocol': 'graphql-ws'}
json={
  "id": "bc270594-8088-4740-b976-5a6048966c3f",
  "payload": {
    "data": "{\"query\":\"subscription UpdatePrice($address: String, $networkId: Int) {\\n        onUpdatePrice(address: $address, networkId: $networkId) {\\n          priceUsd\\n          timestamp}\\n      }\",\"variables\":{\"address\":\"0xf19547f9ed24aa66b03c3a552d181ae334fbb8db\",\"networkId\":42161}}",#这里写合约地址和链的编号
    "extensions": { 
      "authorization": {
        "host": "realtime.api.defined.fi",
        "Authorization": "042J22trve3hqIDndKqxR7Y9vyCc9gQL8CP29lXz"
      }
    }
  },
  "type": "start"
}
async def push(title, content):
    json = {
        "token": "e73179f25ade41729eae654a2decec15",
        "title": title,
        "content": content,
        "topic": "1",
        "template": "html"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url='http://www.pushplus.plus/send/', json=json) as res:
            print(res.status)
async def startup():
    high_prices=[2.74*i for i in range(1,6)]#这里设置止盈提醒价格比如2.74的1到5倍
    low_prices=[0.1,0.05,0.04,0.03]#这里设置止损提醒价格

    async with aiohttp.ClientSession().ws_connect(url=remote, proxy='http://127.0.0.1:10810', headers=headers) as aws:#这里走代理
        await aws.send_json(json)
        while 1:
            try:
                # print('-----------------------------------')
                recv_text = await aws.receive_json()
                print(recv_text)
                price=recv_text.get('payload',{}).get('data',{}).get('onUpdatePrice',{}).get('priceUsd',None)
                if price:
                    if price >= high_prices[0]:
                        high_prices.pop(0)
                        await push('币价提醒',price)
                    elif price <= low_prices[0]:
                        low_prices.pop(0)
                        await push('币价提醒',price)
            except:
                await aws.send_json(json)



if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(startup())
    except Exception as e:
        print('退出', e)