import asyncio
import random
import time
import discord
import re
import datetime
import aiohttp

# GETS THE CLIENT OBJECT FROM DISCORD.PY. CLIENT IS SYNONYMOUS WITH BOT.
intents = discord.Intents.all()
bot = discord.Client(intents=intents, proxy='http://127.0.0.1:1081')
msgs=[]
#获取对应的剧本，写入列表
with open('msg0.txt', 'r+', encoding='utf-8') as fp:
    for i in [line.strip('\n') for line in fp.readlines()]:
        if i not in msgs:
            msgs.append(i)


# EVENT LISTENER FOR WHEN THE BOT HAS SWITCHED FROM OFFLINE TO ONLINE.
@bot.event
async def on_ready():
    # CREATES A COUNTER TO KEEP TRACK OF HOW MANY GUILDS / SERVERS THE BOT IS CONNECTED TO.
    guild_count = 0
    # LOOPS THROUGH ALL THE GUILD / SERVERS THAT THE BOT IS ASSOCIATED WITH.
    for guild in bot.guilds:
        # PRINT THE SERVER'S ID AND NAME.
        print(f"- {guild.id} (name: {guild.name})")
        # INCREMENTS THE GUILD COUNTER.
        guild_count = guild_count + 1

    # PRINTS HOW MANY GUILDS / SERVERS THE BOT IS IN.
    print("SampleDiscordBot is in " + str(guild_count) + " guilds.")
    channel = bot.get_channel(1036569767236083712)#刷经验的频道id
    while 1:
        try:
            async with channel.typing():
                # simulate something heavy
                await asyncio.sleep(1)
            # await channel.send(msgs[random.randint(0,len(msgs)-1)])
            await channel.send('/work\n\n')
            print('ok')
        except:
            print('error')
            continue
        await asyncio.sleep(random.randint(10,30))


# EVENT LISTENER FOR WHEN A NEW MESSAGE IS SENT TO A CHANNEL.
# @bot.event
# async def on_message(message):
#     # CHECKS IF THE MESSAGE THAT WAS SENT IS EQUAL TO "HELLO".
#     print(bot.user.name, message.guild.name, message.channel.name, message.author.name, message.content)
#     # 接蜥蜴的话
#     # if message.channel.id == 1036569767236083712 and message.author.name != bot.user.name:
#     #     await asyncio.sleep(random.randint(5, 30))
#     #     async with message.channel.typing():
#     #         await asyncio.sleep(1)
#     #     await message.channel.send(msgs[random.randint(0,len(msgs)-1)])
#     #被提及的反应
#     if bot.user.id in message.raw_mentions:
#         async with message.channel.typing():
#             # simulate something heavy
#             await asyncio.sleep(3)
#         await message.reply('!')
#     #被回复的反应
#     if message.reference and bot.user.name in message.reference.resolved.author.name:
#         print('被提及',message.content,message.reference.resolved.content)
#         if re.findall(r'bot|机器',message.content,re.I):
#             async with message.channel.typing():
#                 # simulate something heavy
#                 await asyncio.sleep(1)
#             await message.reply('no👋')
#         else:
#             async with message.channel.typing():
#                 # simulate something heavy
#                 await asyncio.sleep(1)
#             await message.reply(msgs.pop(0))#回复
#             #await message.add_reaction('🎉')

# @bot.event
# #监听反应
# async def on_reaction_add(reaction,user):
#     print(reaction.emoji)
#     await reaction.message.add_reaction(reaction.emoji)#做出一样的反应
# EXECUTES THE BOT WITH THE SPECIFIED TOKEN. TOKEN HAS BEEN REMOVED AND USED JUST AS AN EXAMPLE.
bot.run("MTAwMTEyNDg1Nzg4MDI2NDcyNA.GATufL.FTl4BJwyMk02nfQHI8ro1a5B7u14X1DuX-zAds")
