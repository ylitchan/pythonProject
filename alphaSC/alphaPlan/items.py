# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class AlphaplanItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass

class TweetlItem(scrapy.Item):
    # define the fields for your item here like:
    tweet_id = scrapy.Field()
    tweet_text = scrapy.Field()
    tweet_media = scrapy.Field()
    tweet_user = scrapy.Field()

