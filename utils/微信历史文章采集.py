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
    'Cookie': 'rewardsn=; wxuin=1071678606; lang=zh_CN; appmsg_token=1283_qO41qQ%2BgQBDYniMYSw_D4gKOAbCnOGToYTEshtN56m-5n2lfws4cOG1rRMEVyWhhn_20glQraN8Axe8G; wxtokenkey=777; pass_ticket=zERnjnOvd41eVMDPdJNa36K8i4QCIacC/XC72u6DkSkFXbbeHcXldflLuheEacs9; devicetype=android-34; version=28003258; wap_sid2=CI6Jgv8DEooBeV9ISkZJT2tyUVNER0d4cTZwMXdJTVhtYlgwWld1RzBSUGx3VEI2NUcwaVBYYjg2V2xZOFpBNENZOTI0eFJxZk1nV2FDb0I5bnhBMG9aWkljY2xjSzRFajhoakVqU0xwaUx5ODZFajN4SDg0XzgteG1WUDhNeXNXU0hGWEo0dUgxWVBlRVNBQUF+MI70kLYGOA1AlU4='}
url_base = 'https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz=MzI4OTkyNDgxNA==&f=json&offset={}&count=10&is_ok=1&scene=124&uin=MTA3MTY3ODYwNg%3D%3D&key=daf9bdc5abc4e8d02104225f505b0c9c03ee6ce3f68d04d217108a19e4d4828ba2ef36978029e46379337f90b794d5a13ed2242c07bee5bb72c5cf76d9e947b8d04450064937570b8d089d4db21e844bbad9e107ccb4bcd8a13a23002b6e075e195b7e6470d8fe041a88e1092aa1ce4787a4c6d4a2bd08bc861b79814f755e0e&pass_ticket=zERnjnOvd41eVMDPdJNa36K8i4QCIacC%2FXC72u6DkSkFXbbeHcXldflLuheEacs9&wxtoken=&appmsg_token=1283_oevn21q7cJjrRBIw-cj4wHw6f-27qnTsu0YB-Q~~&x5=0&f=json'


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
        with open(f'./军鹰/{report_datetime.strftime("%Y年%m月%d日")}{title.replace("|", "、").replace("/", "、")}.html',
                  'wb') as f:
            f.write(res.content)
    except Exception as e:
        print('错误', title, str(e))
    for j in i['app_msg_ext_info'].get('multi_app_msg_item_list', []):
        title = j['title']
        print(report_datetime, title)
        try:
            res = session.get(j['content_url'].replace('amp;', '').replace('#wechat_redirect', ''))
            res.raise_for_status()
            with open(
                    f'./军鹰/{report_datetime.strftime("%Y年%m月%d日")}{title.replace("|", "、").replace("/", "、")}.html',
                    'wb') as f:
                f.write(res.content)
        except Exception as e:
            print('错误', title, str(e))


if __name__ == '__main__':
    main()
