import os

import telebot
import tweepy
import json
import pymongo
import asyncio

# from discord_webhook import DiscordWebhook, DiscordEmbed
ISHTARider_tg = telebot.TeleBot(os.environ.get("ISHTARider_tg"))
# bearer_token = "AAAAAAAAAAAAAAAAAAAAAPEGjQEAAAAAREb6WuXu7rNwm8ChnkpJoSJmSkw%3DXgtd6IlBg9SyrAcVhTOVucCrYL4OGfSjjCmMbfM8mFTi3CqUcL"
client = tweepy.Client(os.environ.get("tweetapi"))
# print(client.get_user(id=1595795085261787140))
mgclient = pymongo.MongoClient('mongodb://localhost:27017/')
mgdb = mgclient['alpha']
# intents = dcDemo.Intents.all()
# bot = dcDemo.Client(intents=intents, proxy='http://127.0.0.1:10810')
with open(r'D:\allProjects\pyDemo\alphaPlan\alpha.json', 'r+') as alpha:
    alpha = json.load(alpha)
    print('====================', len(alpha))


# 定义获取following的函数
async def get_following(user_id):
    alert = []  # 新增的following放入提醒
    collection = mgdb[alpha[user_id]]  # 该alpha的关注数据集
    fields = []
    print('这是collection', collection)
    res = client.get_user(id=user_id, user_fields=["profile_image_url"])
    tx = res.data.profile_image_url  # 获取头像
    response = client.get_users_following(
        user_id, user_fields=["profile_image_url", "public_metrics", 'created_at', 'description'], max_results=1000
    )
    if response.data and collection.estimated_document_count() != 0:  # 避免无关注和新degen
        for user in response.data:
            print(user.username, user.name, user.profile_image_url)
            if user.username not in str(collection.find_one({'name': user.username})):
                collection.insert_one({'name': user.username})
                data = mgdb['count'].find_one({'name': user.username})
                if data:  # 更新数据库中的数据
                    data['number'] += 1
                    mgdb['count'].update_one({'name': user.username}, {'$set': data})
                    if data['number'] >= 0.15 * len(alpha):
                        fields.append({'name': user.username + 'のdetail',
                                       'value': 'https://twitter.com/' + user.username + '\n' + '\n'.join(
                                           str(user.public_metrics)[1:-1].split(',')) + '\n简介:\n' + user.description,
                                       'inline': False})
                        alert.append(user.username + '目前degen关注数: ' + str(data['number']) + '/' + str(
                            len(alpha)) + '\n创建于' + str(user.created_at))
                else:  # 把新数据插入数据库
                    mgdb['count'].insert_one({'name': user.username, 'number': 1})
    elif response.data and collection.estimated_document_count() == 0:  # 对新degen初始化数据
        for user in response.data:
            print(user.username, user.name, user.profile_image_url)
            collection.insert_one({'name': user.username})
            data = mgdb['count'].find_one({'name': user.username})
            if data:  # 更新数据库中的数据
                data['number'] += 1
                mgdb['count'].update_one({'name': user.username}, {'$set': data})
            else:  # 把新数据插入数据库
                mgdb['count'].insert_one({'name': user.username, 'number': 1})
    if alert:
        ISHTARider_tg.send_message(-1001982993052, '\n'.join(alert))
        # webhook = DiscordWebhook(
        #     url='https://discord.com/api/webhooks/1048054552324214804/b6DTFVsbgeedHqlR3xQjVT78KQBPs2LxWofuxirJJNj3ml2IoK0PuXmlVHRDCwj7AMsb',
        #     embeds=[{"author": {"name": alpha[user_id], "icon_url": "https://api.cyfan.top/acg",
        #                         "url": 'https://twitter.com/' + alpha[user_id]},
        #              "title": '新增关注',
        #              "description": '\n'.join(alert),
        #              "fields": fields,
        #              "thumbnail": {"url": tx},
        #              "image": {"url": "https://pbs.twimg.com/profile_banners/1568898000654680064/1669021682/1500x500"},
        #              "footer": {"text": 'UST DAO投研社区',
        #                         "icon_url": "https://pbs.twimg.com/profile_images/1594618627227062274/4cCvmcws_400x400.jpg",
        #                         "url": "https://twitter.com/dao_ust"}, }],
        #     # content='following新增',
        #     username='Beast',
        #     avatar_url='https://api.cyfan.top/acg')
        # webhook.api_post_request()


async def main():
    # Get User's Followers
    # This endpoint/method returns a list of users who are followers of the
    # specified user ID

    # user_id = 1557705349846614016

    # By default, only the ID, name, and username fields of each user will be
    # returned
    # Additional fields can be retrieved using the user_fields parameter
    num = 0
    while True:
        for user_id in alpha:
            # try:
            if num < 15:  # 每15个等待15分钟
                num += 1
                await get_following(user_id)
                print('=============================', num)

            else:
                print('=========等待刷新==========')
                await asyncio.sleep(910)
                num = 1
                await get_following(user_id)
                print('========刷新完毕===========', num)
            # except:
            #     print('=========error==========')

        # for l in range(len(alphafollowing)):  # 获取计数
        #     count = alphafollowing.count(alphafollowing[l])
        #     condition = {'name': alphafollowing[l]}
        #     data = mgdb['count'].find_one(condition)
        #     if data:  # mg数据库更新
        #         data['number'] = count
        #         mgdb['count'].update_one(condition, {'$set': data})
        #     else:  # mg数据库插入
        #         mgdb['count'].insert_one({'name': alphafollowing[l], 'number': count})
        # alphafollowing.clear()

        # By default, this endpoint/method returns 100 results
        # You can retrieve up to 1000 users by specifying max_results
        # response = client.get_users_following(user_id, max_results=3000)


if __name__ == '__main__':
    asyncio.run(main())
