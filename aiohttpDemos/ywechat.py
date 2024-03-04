import aiohttp
from aiohttp import web
import datetime
import requests
import json
import logging
async def handle(request):
    name = request.match_info.get('name', "Anonymous")  # 获取name
    print(datetime.datetime.now())  # 触发视图函数的时间
    data = await request.json()  # 等待post数据完成接收，只有接收完成才能进行后续操作.data['key']获取参数
    message=data['data']
    print(message,dir(message))
    if message['content'].startswith('!hello'):
        print(message['content'],dir(message['content']))
        data = {"wId": "11975fe7-403c-43f3-9e22-3c8ce683eda8","wcId": '25858910715@chatroom',"content": "hello\n"+message['fromUser']}
        heards={'authorization':'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxNzg4MDM1NjQ4MSJ9.pFKEyy_0kBT1WKMy7sGnbBjEORtTKI6u0RGoH-R5pCiHZ5CBFG1s4TD80YYPezi4HLW4jTQ2niUH_fRJWCeqEw','Content-Type':'application/json'}
        requests.post('http://114.107.252.79:9899/sendText',data=json.dumps(data),headers=heards)
        # async with aiohttpDemos.ClientSession() as session:
        #     async with session.post('http://114.107.252.79:9899/sendText', data=data,heards=heards) as response:
        #         print(await response.text())
    #print(datetime.datetime.now(),data.data.fromUser)  # 接收post数据完成的时间
    return web.Response(text="Hello, world")


app = web.Application()
app.router.add_post('/', handle)
app.router.add_get('/{name}', handle)

web.run_app(app,host='127.0.0.1',port=8080)