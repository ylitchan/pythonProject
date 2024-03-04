# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
import re

import openai
import pytesseract
import requests
import telebot
from PIL import Image
# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

import pymongo

bot = telebot.TeleBot("6291256191:AAExAaaagpZgEAdBvhOMRN2JxlXr8om4qJA")
openai.api_key = "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"


class AlphaplanPipeline:
    def process_item(self, item, spider):
        return item


class TweetPipeline(object):
    def __init__(self):
        super().__init__()
        myclient = pymongo.MongoClient("mongodb://localhost:27017/")
        self.collection = myclient['alpha']['launchTrack']

    def chatGPT(self, msg: list):
        res = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=msg
            # messages=[
            #     {"role": "user", "content": "未成年人不应该浏览哪些网址，列举20个"},
            # ]
        )
        return u"%s" % res['choices'][0]['message']['content']

    def process_item(self, item, spider):
        if not self.collection.find_one({'tweet_id': item['tweet_id']}) and re.findall(
                    r'\blaunch\b|sale|release|live|list|发射|fire|available|time|liquidity|contract|address|stealth|airdrop', item['tweet_text'], re.I):
            if item['tweet_media']:
                res = requests.get(item['tweet_media'], stream=True)
                with open('alpha.png', 'wb') as file:
                    # 每128个流遍历一次
                    for data in res.iter_content(128):
                        # 把流写入到文件，这个文件最后写入完成就是，selenium.png
                        file.write(data)  # data相当于一块一块数据写入到我们的图片文件中
                media_text = pytesseract.image_to_string(Image.open('alpha.png'), lang='chi_sim+eng')
            else:
                media_text = ''
            tweet_text = item['tweet_text'] + '\n' + media_text

            msg = [{"role": "assistant", "content":"sale:unknown,launch:unknown,listing:unknown,liquidity providing:unknown,airdrop:unknown"},{"role": "user","content": tweet_text + '\n按照之前的格式提取以上内容中代币sale时间/代币launch时间/代币listing时间/代币liquidity providing时间/代币airdrop时间,若时间为现在则为now,若为其他情况则为unknown'}]

            hf = self.chatGPT(msg)
            print(len(re.findall(r'unknown', hf, re.I)))
            if len(re.findall(r'unknown',hf,re.I))<5 and ':' in hf:
                bot.send_message(-980470620,
                                 '@' + item['tweet_user'] + '\n' + hf + '\n详见以下推文https://twitter.com/' + item[
                                     'tweet_user'] + '/status/' + item['tweet_id'] + '\n' + item['tweet_text'])
                # bot.send_message(-817780624,
                #                  '@' + item['tweet_user'] + '\n' + hf + '\n详见以下推文https://twitter.com/' + item[
                #                      'tweet_user'] + '/status/' + item['tweet_id'] + '\n' + item['tweet_text'])
            # await push('launch',tweet.text)
            print(tweet_text, hf, sep='\n')
            item['tweet_text'] = tweet_text
            self.collection.insert_one(dict(item))

        return item








