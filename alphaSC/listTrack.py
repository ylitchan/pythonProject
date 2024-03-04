import asyncio
import re
from pprint import pprint
import telebot
import tweepy
from notion_client import Client
import openai
import pymongo
mgclient = pymongo.MongoClient('mongodb://localhost:27017/')
bearer_token = "AAAAAAAAAAAAAAAAAAAAAPEGjQEAAAAAREb6WuXu7rNwm8ChnkpJoSJmSkw%3DXgtd6IlBg9SyrAcVhTOVucCrYL4OGfSjjCmMbfM8mFTi3CqUcL"
client = tweepy.Client(bearer_token)
bot = telebot.TeleBot("6291256191:AAExAaaagpZgEAdBvhOMRN2JxlXr8om4qJA")
openai.api_key = "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"
messages=[{"role": "assistant", "content":"发售时间:false,发射时间:false,发行时间:false"}]
attach='\n提取以上内容中项目的发射或发售或发行时间并在对应项写true和时间，如果正在发射或发售或发行则在对应项写true和正在进行'
# notion = Client(auth='secret_MpgBIGfzOFKxxVJPP3leFyKwFUUjuGTH5F8ZUBG34ZJ')
collection = mgclient['alpha']['listTrack']
async def chatGPT(msg: list):
    res = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=msg
        # messages=[
        #     {"role": "user", "content": "未成年人不应该浏览哪些网址，列举20个"},
        # ]
    )
    return u"%s" % res['choices'][0]['message']['content']

async def main():
    # Get User's Followers
    # This endpoint/method returns a list of users who are followers of the
    # specified user ID

    # user_id = 1557705349846614016

    # By default, only the ID, name, and username fields of each user will be
    # returned
    # Additional fields can be retrieved using the user_fields parameter
    while True:
        for i in ['1567732782700367875','1622670732416229393','1620704962530643973']:
            try:
                print(i)
                res = client.get_list_tweets(i, max_results=1,expansions="author_id",user_fields='username')
                tweet_id=res.data[0].id
                tweet_text=res.data[0].text
                pprint(tweet_text)
                if not collection.find_one({'tweet_id': tweet_id}) and re.findall(
                        r'\blaunch\b|sale|release|live|list|发射|fire|available|time', tweet_text, re.I):
                    msg = messages + [{"role": "user", "content": tweet_text + attach}]
                    # print(msg)
                    hf = await chatGPT(msg)
                    if 'true' in hf:
                        username = res.includes['users'][0].username
                        bot.channel.send_message(-980470620,
                                         '@' + username + '\n' + hf + '\n详见以下推文https://twitter.com/' + username + '\n' + tweet_text)
                    # await push('launch',tweet.text)
                    print(tweet_text, hf, sep='\n')
                    collection.insert_one({'tweet_id': tweet_id})
                #pprint(tweet_text)
            except:
                print(i,'出现错误')
                continue
        await asyncio.sleep(3)





if __name__ == '__main__':
    asyncio.run(main())