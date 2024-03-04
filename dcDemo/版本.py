# -*- encoding=utf8 -*-
__author__ = "颜立全"

import random
import time

import requests
# from airtest.core.api import *

# auto_setup(__file__)


# from poco.drivers.android.uiautomation import AndroidUiautomationPoco
# poco = AndroidUiautomationPoco(use_airtest_input=True, screenshot_each_action=False)
import asyncio
import json
import discord
import re
import datetime
import aiohttp
import requests
import sys




# sys.path.append('D:\PycharmProjects\demos\itchatDemo\itchatuos.py')
#聊天api
async def chatGPT(gjc):
    rsp=requests.post('https://api.forchange.cn/', json={"prompt": "Human:"+gjc+"\nAI:"})
    return rsp.json()['choices'][0]['text']

# 微信消息
# def vrun():
#     @itchat.msg_register(TEXT, isGroupChat=True)
#     def text_reply(msg):
#         print(msg.FromUserName,msg.text)
#         if msg.FromUserName == '@@d03494479a48eb4b26a303d8d4e1246ed53c17e47a0d8a61f43c9d37e714f6d1' and msg.isAt:
#             a=msg.text.replace('@ylitchan ','')
#             msg.user.send(floor(a))
#         elif msg.FromUserName == '@@35d07ec9a7bcdde5f1a70f00aa5b483b55df6ad6328448117d0caf54a7d3c262' and '牛奶' in msg.text:
#             itchat.search_friends(name='女人')[0].send(msg.text)
#     itchat.run(True)


# 初始化数据
# monlist = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
# with open('doneguild.json', 'r+', encoding='utf-8') as fp:
#     doneguild = json.load(fp)
#     nowmday = [doneguild.pop()]
#地板价查询
# async def floor(slug):
#     nft=requests.get('https://app.nfttrack.ai/api/search?q='+slug).json()['data']['collections'][0]['opensea_slug']
#     res=requests.get('https://app.nfttrack.ai/api/collection_info/'+nft)
#     return nft+'地板：'+str(res.json()['data']['floor_price'])
# 该函数用于发送推送到微信
# async def push(title, content):
#     json = {
#         "token": "e73179f25ade41729eae654a2decec15",
#         "title": title,
#         "content": content,
#         "topic": "1",
#         "template": "html"
#     }
#     async with aiohttp.ClientSession() as session:
#         async with session.post(url='http://www.pushplus.plus/send/', json=json) as res:
#             print(res.status)


# CREATES A COUNTER TO KEEP TRACK OF HOW MANY GUILDS / SERVERS THE BOT IS CONNECTED TO.
# async def count():
#     mon = datetime.datetime.now().timetuple().tm_mon
#     mday = datetime.datetime.now().timetuple().tm_mday
#     if mday != nowmday[-1]:  # 每日刷新已扫描服务器
#         doneguild.clear()
#     guild_count = 0
#     # LOOPS THROUGH ALL THE GUILD / SERVERS THAT THE BOT IS ASSOCIATED WITH.
#     for guild in bot.guilds:
#         # PRINT THE SERVER'S ID AND NAME.
#         print(f"- {guild.id} (name: {guild.name})")
#         if guild.name not in doneguild:
#             price = []  # 频道全称
#             month = []  # mint月份
#             alert = []  # mint日期
#             for channel in guild.channels:
#                 # 匹配关键字过滤信息
#                 if re.findall(r'mint|date|day|sale|price|cost|free|time', channel.name, re.I):
#                     price.append(channel.name)
#                     for i in range(0, 12):
#                         try:
#                             if re.findall(monlist[i], channel.name, re.I):
#                                 month.append(i + 1)
#                                 try:
#                                     alert.append(int(re.findall(r'\d+', channel.name, re.I)[0]))
#                                 except:
#                                     alert.append(0)
#                                 break
#                             elif i == 11 and '/' in channel.name:
#                                 month.append(int(re.findall(r'\d+', channel.name, re.I)[0]))
#                                 alert.append(int(re.findall(r'\d+', channel.name, re.I)[1]))
#                         except:
#                             continue
#                     print(channel.name)
#             for l in range(0, len(month)):
#                 if mday - alert[l] in (0, -1) and month[l] == mon:
#                     if mday - alert[l] == -1:
#                         djs = '明天'
#                     else:
#                         djs = '今天'
#                     await push(guild.name + ' mint提醒', djs + 'mint\n' + '\n'.join(price))
#                     await bot.get_channel(993422944791429150).send(guild.name+' mint提醒\n'+djs + 'mint\n' + '\n'.join(price))
#                     await bot.get_channel(1036569767236083712).send(guild.name+' mint提醒\n'+djs + 'mint\n' + '\n'.join(price))
#
#             doneguild.append(guild.name)
#             # INCREMENTS THE GUILD COUNTER.
#         guild_count = guild_count + 1
#     nowmday[-1] = datetime.datetime.now().timetuple().tm_mday
#     doneguild.append(nowmday[-1])
#     with open('doneguild.json', 'w+', encoding='utf-8') as fp:
#         json.dump(doneguild, fp)
#     # PRINTS HOW MANY GUILDS / SERVERS THE BOT IS IN.
#     print("SampleDiscordBot is in " + str(guild_count) + " guilds.")


# GETS THE CLIENT OBJECT FROM DISCORD.PY. CLIENT IS SYNONYMOUS WITH BOT.
intents = discord.Intents.all()
bot = discord.Client(intents=intents, proxy='http://127.0.0.1:10810')
@bot.event
async def on_ready():
    while True:
        await bot.get_channel(1085995494796447795).send()
        await asyncio.sleep(14400)

# EVENT LISTENER FOR WHEN THE BOT HAS SWITCHED FROM OFFLINE TO ONLINE.
# @bot.event
# async def on_ready():
#     while True:
#         await count()
#         await asyncio.sleep(14400)


# EVENT LISTENER FOR WHEN A NEW MESSAGE IS SENT TO A CHANNEL.
@bot.event
async def on_message(message):
    print(bot.user.name, message.channel.id,message.guild.name, message.channel.name, message.author.name, message.content)
#     # 判断消息是否是关于mint或者钱包地址提交
#     if re.findall(r'submi', message.content, re.I) and re.findall(r'@everyone', message.content, re.I) and re.findall(r'addr|wallet', message.content, re.I):
#         await push(message.guild.name + ' announcement',
#                    'channel:\n' + message.channel.name + '\nauthor:\n' + message.author.name + '\ncontent:\n' + message.content)
    # elif message.channel.name == 'bot':
    #     room = poco(text="DAY")[0]
    #     room.click()
    #     poco("com.tencent.mm:id/iki").click()
    #     text(message.content)
    #     poco("com.tencent.mm:id/uo").click()

    if message.channel.id in [945930620230578246] and message.author.name != bot.user.name:
        a = random.randint(0, 10)
        if a >= 5:
            # try:
            #     spliter = re.search(r'[，。！？,.?!]', message.content).group()
            #     huifu = message.content.split(spliter)[0]
            #     print('=============', huifu)
            # except:
            #     huifu=message.content
            #     # if not re.findall(r'人工智能', huifu):
            #     # if a >= 8:
            #     #     await message.reply(huifu)
            #     # else:
            # finally:
            async with bot.get_channel(1073989056565878796).typing():
                # simulate something heavy
                await bot.get_channel(1073989056565878796).send(message.content)
    elif message.channel.id in [1073989056565878796,1073947096807391283] and message.author.name != bot.user.name:
        a=random.randint(0,10)
        if a>=50:
            async with message.channel.typing():
                # simulate something heavy
                huifu=await chatGPT(message.content)
                print(huifu)
                try:
                    spliter=re.search(r'[，。！？,.?!]',huifu).group()
                    huifu=huifu.split(spliter)[0]
                    print('=============',huifu)
                except:
                    pass
                # if not re.findall(r'人工智能', huifu):
                if a >= 8:
                    await message.reply(huifu)
                else:
                    await message.channel.send(huifu)

#     # 推送alphabot消息，抓抽奖
#     if message.author.name == 'Alphabot' and message.embeds:
#         await push(message.guild.name + ' Alphabot',
#                    'channel:\n' + message.channel.name + '\nauthor:\n' + message.author.name + '\nembed title:\n' +
#                    message.embeds[-1].title + '\nembed description:\n' + message.embeds[-1].description)
#     # 被提及的消息
#     if bot.user.id in message.raw_mentions:
#         await push(message.guild.name + ' mention u',
#                    'channel:\n' + message.channel.name + '\nauthor:\n' + message.author.name + '\ncontent:\n' + message.content)
#     # 被回复的消息
#     if message.reference and bot.user.name in message.reference.resolved.author.name:
#         await push(message.guild.name + ' reply u',
#                    'channel:\n' + message.channel.name + '\nauthor:\n' + message.author.name + '\ncontent:\n' + message.content + '\nrelpy2:\n' + message.reference.resolved.content)


# EXECUTES THE BOT WITH THE SPECIFIED TOKEN. TOKEN HAS BEEN REMOVED AND USED JUST AS AN EXAMPLE.
# p = Process(target=vrun)
# p.daemon=True
# p.start()
bot.run('MTAwMTEyNDg1Nzg4MDI2NDcyNA.GBOmUj.18XSjoKckfI9n4HNlZqBQXRNIUweeulpglOIwA')
