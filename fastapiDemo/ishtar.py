import asyncio
import json
import os
import random
import re
from jsonpath_ng import parse
import openai
import requests
import tweepy
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
import uvicorn
import telebot


# openai.api_key = os.getenv("openai")
#
# # 创建生产者实例
# producer = KafkaProducer(bootstrap_servers=['localhost:9092'])
#
app = FastAPI()
# bot = telebot.TeleBot(os.getenv("ISHTAR"))
# user_dict={}
# ts_dict={}
# @app.post("/")
# async def root(json=Body(None)):
#     return {"message": "Received Tg event"}


#     print('=================')
#     text = json.get('message', {}).get('text', '')
#     chat_id = json.get('message', {}).get('chat', {}).get('id', 0)
#     if chat_id==5341501065 or chat_id==5865410419:
#         print(text)
#         a=re.findall(r'@.*?\n',text)
#         for i in a:
#             try:
#                 user_id=client.get_user(username=i.replace('\n','').replace('@','')).data.id
#                 print(user_id)
#                 # a=client.add_list_member(id=1639838455760035840,user_id=user_id)
#                 # print(a)
#                 # all.add(user_id)
#                 # 发送消息
#                 print(str(user_id).encode('utf-8'))
#                 producer.send('test', str(user_id).encode('utf-8'))
#                 #client.add_list_member(id=1639838455760035840,user_id=user_id)
#             except:
#                 continue
#vx小程序的请求
# @app.post("/ishtarider")
# async def events(json=Body(None)):
#     open_id = parse('$..open_id').find(json)[0].value
#     while True:
#         user=user_dict.get(open_id, '')
#         if user:
#             break
#
#     return {"message": "Received Slack event"}
#     # print('===================================',json)
#     user = parse('$..user').find(json)[0].value
#     msg = parse('$..text').find(json)[0].value
#     if not re.search(r'_*Please note|_Typing…_', msg) and 'U053GBTT1J8' not in user:
#         print(msg)
#
#     if "challenge" in json:
#         # Respond to the Slack challenge
#         return {"challenge": json["challenge"]}
#
#     # Handle other Slack events here
#     # ...
#
#     return {"message": "Received Slack event"}

@app.get('/')
async def ishtar():
    return {'asodjfoasdifiosd'}
@app.post("/ishtarider")
async def ishtarcher(json=Body(None)):
    print(json)
    if "challenge" in json:
        # Respond to the Slack challenge
        return {"challenge": json["challenge"]}
    # print(parse('$..text').find(json)[0].value)
    # thread_ts =parse('$..text').find(json)
    # if thread_ts:
    #     text = parse('$..text').find(json)[0].value
    #     thread_ts=thread_ts[0].value
    #     msg=ts_dict.get(thread_ts,[])
    #     if msg:
    #         msg.insert(0,text)
    #         msg=msg[:50]
    # channel = parse('$..channel').find(json)[0].value
    # bot_id = parse('$..bot_id').find(json)
    # if channel == 'D054NGFG2TY' and not bot_id:
    #     producer.send('ISHTARcher', parse('$..text').find(json)[0].value.encode('utf-8'))
    #
    # return {"message": "Received Slack event"}
    # print('===================================',json)
    # user = parse('$..user').find(json)[0].value
    # msg = parse('$..text').find(json)[0].value
    # if not re.search(r'_*Please note|_Typing…_', msg) and 'U053GBTT1J8' not in user:
    #     print(msg)

    # if "challenge" in json:
    #     # Respond to the Slack challenge
    #     return {"challenge": json["challenge"]}


# return {"message": "Received Slack event"}


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=80)
