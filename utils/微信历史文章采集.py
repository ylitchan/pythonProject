import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from requests import Session, packages

packages.urllib3.disable_warnings()
session = Session()
session.verify = False
session.headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 NetType/WIFI MicroMessenger/7.0.20.1781(0x6700143B) WindowsWechat(0x63090b13) XWEB/11097 Flue',
    'Cookie': 'wxuin=344605199; lang=zh_CN; rewardsn=; wxtokenkey=777; appmsg_token=1280_3JH3zNMj8fRaaC2OvJ5WVUQjYX8lqm8GXqCaaa_tSC_V-vFVxQzvQmPSkrNjqkIyPlJkBJ1ILzQMtiw2; devicetype=android-34; version=28003254; pass_ticket=vFHsiXKu8PfkHx4eIqwMimF4/rvsCofeI5MjAqwzkS1bkHzxhOAbixdNlk1EUZ; wap_sid2=CI+EqaQBEooBeV9IRkN3eXNFWkItMEJQcFdxQ2pvRGZzSXpEQjFpQmRqUDFwN1VFOXdNdkFnOWlHNEhVd1ppenJqVTF4TzNnMnlfNW5JRnlnSU5PQVJxOTdHXy1vNUpUSmt0SlFTamE0bXFnVXVwZ2F3TWQ1cENnWHpHUWF6MkhOb1JjLVdCWDRCNE1kMFNBQUF+MMCejbUGOA1AlU4='}
url_base = 'https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz=MzA3NDMxOTQwNw==&f=json&offset=11&count=10&is_ok=1&scene=124&uin=MzQ0NjA1MTk5&key=daf9bdc5abc4e8d095249f9e3110006c96b935914844d6e2fbbc7f68b42a22c2f06ea7a08cc90bedbec2375b1125ef78610384446a02ddb681f3945fa2d5ad46f4aba482d9f3a6748b3e41ea4201b6b165865bc6f02aae687b753e0507362ef076b8577116463d8ab07a2f5316eb5e6dd50e43fe242c8c7027b5c18d2657ca3b&pass_ticket=lagu5HQ0LKh%2Fxb38cQchMdD1pSEdf9YhDTcZiT11Ffh1XjhinNOlaaHTPud16C6%2F&wxtoken=&appmsg_token=1280_DILNtMzNRnAbSTP17zWEyd72Jgmw0Gp1L15Yig~~&x5=0&f=json'


def main():
    page = 0
    thread_pool = ThreadPoolExecutor(max_workers=100)
    while 1:
        print('当前页', page)
        try:
            url = url_base.format(page)
            res = session.get(url)
            res.raise_for_status()
            res_json = res.json()
            res_json = json.loads(res_json['general_msg_list'])
            if res_json['list'][-1]['comm_msg_info']['datetime'] < 1577808000:
                break
            futures = [thread_pool.submit(parse_detail, i) for i in res_json['list']]
            for future in as_completed(futures):
                future.result()
        except:
            break
        page += 10
        time.sleep(30)
    thread_pool.shutdown()


def parse_detail(i):
    report_time = i['comm_msg_info']['datetime']
    report_datetime = datetime.fromtimestamp(report_time)
    title = i['app_msg_ext_info']['title']
    print(report_datetime, title)
    if report_time < 1577808000:
        return
    try:
        res = session.get(i['app_msg_ext_info']['content_url'].replace('amp;', '').replace('#wechat_redirect', ''))
        res.raise_for_status()
        with open(f'./知远/{report_datetime.strftime("%Y年%m月%d日")}{title.replace("|", "、").replace("/", "、")}.html',
                  'wb') as f:
            f.write(res.content)
    except Exception as e:
        print('错误', title, str(e))


if __name__ == '__main__':
    main()
