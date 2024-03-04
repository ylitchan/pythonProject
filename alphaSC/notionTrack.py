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
notion = Client(auth='secret_xTyerEZhldQuGspxVIkUm0OE0JPr0Y488YMC4eeR4Ud')
collection = mgclient['alpha']['notionTrack']
async def chatGPT(msg: list):
    res = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=msg
        # messages=[
        #     {"role": "user", "content": "未成年人不应该浏览哪些网址，列举20个"},
        # ]
    )
    return u"%s" % res['choices'][0]['message']['content']

async def get_tweet(user_id,username):
    print(user_id)
    res = client.get_users_tweets(id=user_id)
    tweet = res.data[0]
    tweet_id = tweet.id
    if not collection.find_one({'tweet_id': tweet_id}) and re.findall(r'\blaunch\b|sale|release|live|list|发射|fire|available',tweet.text,re.I):
        msg = messages + [{"role": "user", "content": tweet.text + attach}]
        #print(msg)
        hf = await chatGPT(msg)
        if 'true' in hf:
            bot.send_message(-952353062, '@'+username+'\n'+hf+'\n详见以下推文https://twitter.com/'+username+'\n'+tweet.text)
        # await push('launch',tweet.text)
        print(tweet.text,hf,sep='\n')
        collection.insert_one({'tweet_id': tweet_id})

async def main():
    # Get User's Followers
    # This endpoint/method returns a list of users who are followers of the
    # specified user ID

    # user_id = 1557705349846614016

    # By default, only the ID, name, and username fields of each user will be
    # returned
    # Additional fields can be retrieved using the user_fields parameter
    while True:
        my_page = notion.databases.query(
            **{
                "database_id": "135c36eae4214c7b93ad19f9c8181006",
                "filter": {
                    "property": "是否已发币/nft",
                    "select": {
                        "equals": "否",
                    },
                },
            }
        )
        pprint(len(my_page['results']))
        print('========')
        await dg(my_page)
async def dg(my_page):
    count=0
    for i in my_page['results']:
        try:
            username=i['properties']['推特名']['rich_text'][0]['plain_text'].replace('@', '')
            print(count,username)
            count+=1
            user_id = client.get_user(
                username=username).data.id
            await get_tweet(user_id,username)
            await asyncio.sleep(3)
        except:
            continue
    if not my_page['has_more']:
        return
    else:
        cursor=my_page['next_cursor']
        my_page = notion.databases.query(
            **{
                "database_id": "135c36eae4214c7b93ad19f9c8181006",
                "start_cursor": cursor,
                "filter": {
                    "property": "是否已发币/nft",
                    "select": {
                        "equals": "否",
                    },
                },
            }
        )
        await dg(my_page)


if __name__ == '__main__':
    asyncio.run(main())