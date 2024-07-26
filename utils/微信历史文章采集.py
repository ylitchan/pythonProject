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
    'Cookie': 'wxuin=610625480; lang=zh_CN; devicetype=android-34; version=28003254; pass_ticket=5vnv6r9/qaCfjduSRkM8G6yO89FBvV0LbLnWLuNRBKegn2tFoQdx0ZWb/pH9FH0; wap_sid2=CMjPlaMCEnZ5X0hQZmxYWU9aT3NnR3UxQ0JhakNUOWxsTmVGWElocnJKVVRjc2ZmZDk5WThtaEhYQVJZV0o3dDd2V3BYZzM5NElsUzRzaHpfU1RZUU9tMnRnMEt6d1dDNzVsZm9GZHJQSl9UWUFUWFVmU1llLTNSSUFBQX5+MOjIjbUGOA1AlU4='}
url_base = 'https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz=MzA3NDMxOTQwNw==&f=json&offset={}&count=10&is_ok=1&scene=124&uin=NjEwNjI1NDgw&key=daf9bdc5abc4e8d0d02af44263afd239bbc4f358410ab5637a1b8af52eee4d3b16740f958fe8f13354018949c70e1c0878e42748f1fb5ac3a5e87a94c2430607322b4024b31393913e8a453a08846c66c52cf35f83525d22cfb8d468818a98c721c7376df433c5c6c39ac21844b69f4377e297471b5edbb6ef52998a576a878b&pass_ticket=0jvBrspYo9hO9%2BqYlSBBzlFFcDX4VKRCygyLrQbo0zb3SVsC%2BDoFmhstbi4BUm%2FY&wxtoken=&appmsg_token=1280_5b2sEcOee3RvIibAnWfaIP7AR5MeGaXqIs-DIQ~~&x5=0&f=json'


def main():
    page = 631
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
