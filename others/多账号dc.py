import random

import discord
import re
import datetime
import requests as req
import asyncio
import threading
import pyperclip
lock=threading.Lock()

def pdc(token):
    fp = [line.strip('\n') for line in open('../dcDemo/msg.txt', 'r+', encoding='utf-8').readlines()]
    # GETS THE CLIENT OBJECT FROM DISCORD.PY. CLIENT IS SYNONYMOUS WITH BOT.
    intents = discord.Intents.all()
    bot = discord.Client(intents=intents,proxy='http://127.0.0.1:10810')
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
        channel=bot.get_channel(1037250292133146695)
        while 1:
            await channel.send(fp.pop())
            await asyncio.sleep(2)



    # EVENT LISTENER FOR WHEN A NEW MESSAGE IS SENT TO A CHANNEL.
    @bot.event
    async def on_message(message):
        # CHECKS IF THE MESSAGE THAT WAS SENT IS EQUAL TO "HELLO".
        if message.channel.id==1037250292133146695 and message.author!=bot.user:
            await message.channel.send(fp.pop())
        print(bot.user.name,message.guild,message.channel,message.author,message.content)
        # if message.author.name == bot.user.name:
        #     # SENDS BACK A MESSAGE TO THE CHANNEL.
        #     await message.delete()


    # EXECUTES THE BOT WITH THE SPECIFIED TOKEN. TOKEN HAS BEEN REMOVED AND USED JUST AS AN EXAMPLE.
    bot.run(token)


def main():
    threadlist=[]
    tokens=['OTgyODc1NjcwODI2ODQ0MjAw.GdKIoT.b9IDWjhMbYV3cR5m3YS6fOhF8aYbwPTm2sPl1o',"OTk5MjM3ODQ0MDc1ODA2NzMz.GLAF6K.3tBwlCtIkUarzNIg7xcDG6TWL1-Q7Kapycx8c8"]
    #janet,蜥蜴,前进四
    for tks in tokens:
        thread=threading.Thread(target=pdc,args=[tks,])
        threadlist.append(thread)
        thread.start()
    for t in threadlist:
        t.join()


if __name__ == '__main__':
    main()