import re

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from lxml import etree

session = requests.Session()
session.proxies = {'https': 'http://127.0.0.1:1081', 'http': 'http://127.0.0.1:1081'}
session.headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0'}
# 创建BlockingScheduler对象
scheduler = BlockingScheduler()


def job():
    text = session.get('https://etherscan.io/gastracker')
    # 创建HTML解析器
    parser = etree.HTMLParser()
    # 解析HTML字符串
    html_tree = etree.fromstring(session.get('https://etherscan.io/gastracker').text, parser)
    # 使用XPath提取数据
    gas = html_tree.xpath('//meta[@name="Description"]/@content')
    if gas:
        gas = int(re.search(r'\d+', gas[0].split('|')[-1]).group())
        if gas <= 14:
            json = {
                "msgtype": "text",
                "text": {'content': f'Gas\nHigh:{gas} gwei'}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=bb15fa90-dee0-4463-896d-2acf26619eaf',
                json=json)


if __name__ == "__main__":
    # job()
    # 设置任务调度
    scheduler.add_job(job, 'cron', minute='00', second='00')

    # 启动调度器
    scheduler.start()
