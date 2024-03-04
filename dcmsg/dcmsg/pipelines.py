# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import re
import pymongo

class DcmsgPipeline:
    def process_item(self, item, spider):
        return item


class MongoPipeline(object):
    def __init__(self, mongo_uri, mongo_db):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
    @classmethod
    def from_crawler(cls, crawler):
        return cls(mongo_uri=crawler.settings.get('MONGO_URI'),
            mongo_db=crawler.settings.get('MONGO_DB')
        )
    def open_spider(self, spider):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
    def process_item(self, item, spider):
        name = item.__class__.__name__
        if not self.db[name].find_one(dict(item)):
            if not re.findall(r'n|\d|>|<|@',item['content'],re.I) :
                self.db[name].insert_one(dict(item))
        return item
    def close_spider(self, spider):
        self.client.close()

class TxtPipeline(object):
    def open_spider(self, spider):
        self.fp=open('msg.txt','a+',encoding='utf-8')
    def process_item(self, item, spider):
        if not re.findall(r'n|\d|>|<|@|g|twitter|http|こん|おは|ちわ',item['content'],re.I) :
            self.fp.write(item['content']+'\n')
        return item
    def close_spider(self, spider):
        self.fp.close()
