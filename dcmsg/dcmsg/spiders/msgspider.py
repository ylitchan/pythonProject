import scrapy
import json
from scrapy import Request
from dcmsg.items import DcmsgItem



class MsgspiderSpider(scrapy.Spider):
    name = 'msgspider'
    allowed_domains = ['dcDemo.com']
    baseurl='https://discord.com/api/v9/channels/1008945014887428216/messages?before={msgid}&limit=50'
    start_urls = baseurl.format(msgid=1039883414687453205)
    count=0
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Edg/107.0.1418.35',
        'authorization': 'MTAwMTEyNDg1Nzg4MDI2NDcyNA.GxLcGA.5Sop7Q7smHPnRp_wC3HqPBgkdy1n43chUlDoI8'}

    def start_requests(self):

        yield Request(self.start_urls, callback=self.parse, dont_filter=True, headers=self.headers,meta={'proxy': 'http://127.0.0.1:10810'})

    def parse(self, response):
        reslist=json.loads(response.text)
        item = DcmsgItem()
        for i in range(len(reslist)):
            try:
                item['content'] = reslist[i]['content']
                yield item
            except:
                continue
        self.count += 1
        if self.count<2000:
            yield Request(
                url=self.baseurl.format(msgid=int(reslist[-1]['id'])), callback=self.parse, dont_filter=True, headers=self.headers,meta={'proxy': 'http://127.0.0.1:10810'})
