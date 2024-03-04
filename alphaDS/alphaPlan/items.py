# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html
import os
import django
import scrapy
from scrapy_djangoitem import DjangoItem
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alphaDS.settings')  # 替换成您的项目名
django.setup()
from alphaApp.models import *


class AlphaplanItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass


class LaunchItem(DjangoItem):
    # define the fields for your item here like:
    django_model = LaunchInfo


class CallerItem(DjangoItem):
    # define the fields for your item here like:
    django_model = CallerInfo
