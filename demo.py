import datetime

import requests
from lxml import etree
from urllib.parse import urljoin
session = requests.Session()
session.verify = False
session.headers = {'Content-Type': 'application/json'}
def send_msg(msg):
    """
    发送消息到企业微信群聊

    :param msg: 要发送的消息内容
    :return: None
    """
    try:
        # 记录当前时间和消息内容
        current_time = datetime.datetime.now()
        print(f"{current_time} - 发送消息: {msg}", flush=True)
        json_msg = {"MsgItem": [
            {"AtWxIDList": ["string"], "ImageContent": "", "MsgType": 0, "TextContent": msg,
             "ToUserName": "cyh1002141700"}]}
        response = session.post(
            'http://192.168.144.199:1238/message/SendTextMessage?key=fe197940-30c1-4cea-a41a-17b461423f83',
            json=json_msg)
        # 检查响应状态（可选）
        if response.status_code != 200:
            print(f"消息发送失败，状态码: {response.status_code}", flush=True)
    except Exception as e:
        print(f"消息发送异常: {str(e)}", flush=True)
        # 记录异常但不中断程序

url = "https://www.ptu.edu.cn/index/zbxx.htm"

headers = {
  'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
  'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
  'Accept-Encoding': "gzip, deflate, br, zstd",
  'Pragma': "no-cache",
  'Cache-Control': "no-cache",
  'sec-ch-ua': "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Microsoft Edge\";v=\"138\"",
  'sec-ch-ua-mobile': "?0",
  'sec-ch-ua-platform': "\"Windows\"",
  'Upgrade-Insecure-Requests': "1",
  'Sec-Fetch-Site': "same-origin",
  'Sec-Fetch-Mode': "navigate",
  'Sec-Fetch-User': "?1",
  'Sec-Fetch-Dest': "document",
  'Referer': "https://www.ptu.edu.cn/index/zbxx/135.htm",
  'Accept-Language': "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
  # 'Cookie': "JSESSIONID=B57E10A4135635757C4E89AA97566552"
}
a=[]
response=requests.request("GET", url, headers=headers)
print(response.text)
html=etree.HTML(response.content.decode())
b=html.xpath('//ul[@class="news-list"]//li[contains(.//a//text(),"出版")]')
for i in b:
    a.append(i.xpath('.//a/@title')[0]+'\n'+urljoin(response.url,i.xpath('.//a/@href')[0]))
send_msg('\n'.join(a))