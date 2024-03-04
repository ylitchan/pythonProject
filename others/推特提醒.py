import re
import threading
import time
from collections import Counter
from selenium.common.exceptions import TimeoutException
import selenium.webdriver.edge.service
from discord_webhook import DiscordWebhook
import json
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from flask import Flask, redirect, url_for, request, render_template
from decimal import Decimal
from functools import reduce

from selenium.webdriver.support import expected_conditions as EC


from selenium.webdriver.support.ui import WebDriverWait
options = webdriver.EdgeOptions()
options.headless = True
service = webdriver.edge.service.Service(executable_path="msedgedriver.exe")  # executable_path="D:/msedgedriver.exe"
heads=['user-agent=Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) '
       'Chrome/104.0.5112.81 Mobile Safari/537.36 Edg/104.0.1293.54', "user-agent=Mozilla/5.0 (Linux; Android 6.0; "
                                                                      "Nexus 5 Build/MRA58N) AppleWebKit/537.36 ("
                                                                      "KHTML, like Gecko) Chrome/103.0.5060.134 "
                                                                      "Mobile Safari/537.36 Edg/103.0.1264.71"]


# driver = webdriver.Edge(options=options, service=service)
# cookies=[
# {
#     "domain": ".twitter.com",
#     "expirationDate": 1723282374,
#     "hostOnly": False,
#     "httpOnly": False,
#     "name": "_ga",
#     "path": "/",
#
#     "secure": False,
#     "session": False,
#     "storeId": "0",
#     "value": "GA1.2.1592855525.1660207657",
#     "id": 1
# },
# {
#     "domain": ".twitter.com",
#     "expirationDate": 1660296774,
#     "hostOnly": False,
#     "httpOnly": False,
#     "name": "_gid",
#     "path": "/",
#
#     "secure": False,
#     "session": False,
#     "storeId": "0",
#     "value": "GA1.2.1395512180.1660207657",
#     "id": 2
# },
# {
#     "domain": ".twitter.com",
#     "hostOnly": False,
#     "httpOnly": True,
#     "name": "_twitter_sess",
#     "path": "/",
#
#     "secure": True,
#     "session": True,
#     "storeId": "0",
#     "value": "BAh7CSIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCFPFS4uCAToMY3NyZl9p%250AZCIlNmI1N2I0YzgyNWExOTI5ODNjYTU4NTZlMjJhYmRhYTY6B2lkIiUyMTRh%250ANWY1YmYyNzFiYzE1MjgxOTEwZTY5YzlmNWRlZg%253D%253D--06cb49ecaab99949260148da8ddf59b85d3f735a",
#     "id": 3
# },
# {
#     "domain": ".twitter.com",
#     "expirationDate": 1817016930,
#     "hostOnly": False,
#     "httpOnly": True,
#     "name": "auth_token",
#     "path": "/",
#
#     "secure": True,
#     "session": False,
#     "storeId": "0",
#     "value": "54a8afe7d691d057a37a1c18b4ea657646147ddd",
#     "id": 4
# },
# {
#     "domain": ".twitter.com",
#     "expirationDate": 1817016930,
#     "hostOnly": False,
#     "httpOnly": False,
#     "name": "ct0",
#     "path": "/",
#
#     "secure": True,
#     "session": False,
#     "storeId": "0",
#     "value": "6599e97c7fef02be93a844622192689f5b9665756f5fa1ac2166c7afcab1e54e148457dcf80c6b5c8a669221ddffa665ddcbf33748d48754a3542c9471313fe6fa2c59b64b4765af6f86b77b65810ccf",
#     "id": 5
# },
# {
#     "domain": ".twitter.com",
#     "expirationDate": 1675759613,
#     "hostOnly": False,
#     "httpOnly": False,
#     "name": "d_prefs",
#     "path": "/",
#
#     "secure": True,
#     "session": False,
#     "storeId": "0",
#     "value": "MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw",
#     "id": 6
# },
# {
#     "domain": ".twitter.com",
#     "expirationDate": 1691732262,
#     "hostOnly": False,
#     "httpOnly": False,
#     "name": "eu_cn",
#     "path": "/",
#
#     "secure": True,
#     "session": False,
#     "storeId": "0",
#     "value": "1",
#     "id": 7
# },
# {
#     "domain": ".twitter.com",
#     "expirationDate": 1722408557,
#     "hostOnly": False,
#     "httpOnly": False,
#     "name": "guest_id",
#     "path": "/",
#
#     "secure": True,
#     "session": False,
#     "storeId": "0",
#     "value": "v1%3A165933655804603375",
#     "id": 8
# },
# {
#     "domain": ".twitter.com",
#     "expirationDate": 1694422013,
#     "hostOnly": False,
#     "httpOnly": False,
#     "name": "guest_id_ads",
#     "path": "/",
#
#     "secure": True,
#     "session": False,
#     "storeId": "0",
#     "value": "v1%3A165933655804603375",
#     "id": 9
# },
# {
#     "domain": ".twitter.com",
#     "expirationDate": 1694422013,
#     "hostOnly": False,
#     "httpOnly": False,
#     "name": "guest_id_marketing",
#     "path": "/",
#
#     "secure": True,
#     "session": False,
#     "storeId": "0",
#     "value": "v1%3A165933655804603375",
#     "id": 10
# },
# {
#     "domain": ".twitter.com",
#     "expirationDate": 1706597730,
#     "hostOnly": False,
#     "httpOnly": True,
#     "name": "kdt",
#     "path": "/",
#
#     "secure": True,
#     "session": False,
#     "storeId": "0",
#     "value": "B99If0dKuArdIQSdwfrzxFqDd6MwZMkoorLmSVAp",
#     "id": 11
# },
# {
#     "domain": ".twitter.com",
#     "expirationDate": 1694422013,
#     "hostOnly": False,
#     "httpOnly": False,
#     "name": "personalization_id",
#     "path": "/",
#
#     "secure": True,
#     "session": False,
#     "storeId": "0",
#     "value": "\"v1_FfioWBMAx/+6QoqS2Ve4Kw==\"",
#     "id": 12
# },
# {
#     "domain": ".twitter.com",
#     "expirationDate": 1691746381,
#     "hostOnly": False,
#     "httpOnly": False,
#     "name": "twid",
#     "path": "/",
#
#     "secure": True,
#     "session": False,
#     "storeId": "0",
#     "value": "u%3D1552450863268245504",
#     "id": 13
# },
# {
#     "domain": "mobile.twitter.com",
#     "hostOnly": True,
#     "httpOnly": False,
#     "name": "lang",
#     "path": "/",
#
#     "secure": False,
#     "session": True,
#     "storeId": "0",
#     "value": "en",
#     "id": 14
# }
# ]
# driver.get("https://twitter.com/")
# for item in cookies:
#     driver.add_cookie(item)
fp = open('twitterfollowing.json', 'r+')
#读取本地文件，载入内存
loadtext=json.loads(fp.read())
#该函数为每个组更新数据
def getsfollowing(group):# ,"yLitchan"
    followinglist = []  #存储每个组
    # 的所有following
    #该函数为每个组的每个id获取following
    def getfollowing(id):
        followingset=set()
        options.add_argument(random.choice(heads))

        driver = webdriver.Edge(options=options, service=service)
        cookies = [
            {
                "domain": ".twitter.com",
                "expirationDate": 1723282374,
                "hostOnly": False,
                "httpOnly": False,
                "name": "_ga",
                "path": "/",

                "secure": False,
                "session": False,
                "storeId": "0",
                "value": "GA1.2.1592855525.1660207657",
                "id": 1
            },
            {
                "domain": ".twitter.com",
                "expirationDate": 1660296774,
                "hostOnly": False,
                "httpOnly": False,
                "name": "_gid",
                "path": "/",

                "secure": False,
                "session": False,
                "storeId": "0",
                "value": "GA1.2.1395512180.1660207657",
                "id": 2
            },
            {
                "domain": ".twitter.com",
                "hostOnly": False,
                "httpOnly": True,
                "name": "_twitter_sess",
                "path": "/",

                "secure": True,
                "session": True,
                "storeId": "0",
                "value": "BAh7CSIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCFPFS4uCAToMY3NyZl9p%250AZCIlNmI1N2I0YzgyNWExOTI5ODNjYTU4NTZlMjJhYmRhYTY6B2lkIiUyMTRh%250ANWY1YmYyNzFiYzE1MjgxOTEwZTY5YzlmNWRlZg%253D%253D--06cb49ecaab99949260148da8ddf59b85d3f735a",
                "id": 3
            },
            {
                "domain": ".twitter.com",
                "expirationDate": 1817016930,
                "hostOnly": False,
                "httpOnly": True,
                "name": "auth_token",
                "path": "/",

                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "54a8afe7d691d057a37a1c18b4ea657646147ddd",
                "id": 4
            },
            {
                "domain": ".twitter.com",
                "expirationDate": 1817016930,
                "hostOnly": False,
                "httpOnly": False,
                "name": "ct0",
                "path": "/",

                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "6599e97c7fef02be93a844622192689f5b9665756f5fa1ac2166c7afcab1e54e148457dcf80c6b5c8a669221ddffa665ddcbf33748d48754a3542c9471313fe6fa2c59b64b4765af6f86b77b65810ccf",
                "id": 5
            },
            {
                "domain": ".twitter.com",
                "expirationDate": 1675759613,
                "hostOnly": False,
                "httpOnly": False,
                "name": "d_prefs",
                "path": "/",

                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "MToxLGNvbnNlbnRfdmVyc2lvbjoyLHRleHRfdmVyc2lvbjoxMDAw",
                "id": 6
            },
            {
                "domain": ".twitter.com",
                "expirationDate": 1691732262,
                "hostOnly": False,
                "httpOnly": False,
                "name": "eu_cn",
                "path": "/",

                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "1",
                "id": 7
            },
            {
                "domain": ".twitter.com",
                "expirationDate": 1722408557,
                "hostOnly": False,
                "httpOnly": False,
                "name": "guest_id",
                "path": "/",

                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "v1%3A165933655804603375",
                "id": 8
            },
            {
                "domain": ".twitter.com",
                "expirationDate": 1694422013,
                "hostOnly": False,
                "httpOnly": False,
                "name": "guest_id_ads",
                "path": "/",

                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "v1%3A165933655804603375",
                "id": 9
            },
            {
                "domain": ".twitter.com",
                "expirationDate": 1694422013,
                "hostOnly": False,
                "httpOnly": False,
                "name": "guest_id_marketing",
                "path": "/",

                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "v1%3A165933655804603375",
                "id": 10
            },
            {
                "domain": ".twitter.com",
                "expirationDate": 1706597730,
                "hostOnly": False,
                "httpOnly": True,
                "name": "kdt",
                "path": "/",

                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "B99If0dKuArdIQSdwfrzxFqDd6MwZMkoorLmSVAp",
                "id": 11
            },
            {
                "domain": ".twitter.com",
                "expirationDate": 1694422013,
                "hostOnly": False,
                "httpOnly": False,
                "name": "personalization_id",
                "path": "/",

                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "\"v1_FfioWBMAx/+6QoqS2Ve4Kw==\"",
                "id": 12
            },
            {
                "domain": ".twitter.com",
                "expirationDate": 1691746381,
                "hostOnly": False,
                "httpOnly": False,
                "name": "twid",
                "path": "/",

                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "u%3D1552450863268245504",
                "id": 13
            },
            {
                "domain": "mobile.twitter.com",
                "hostOnly": True,
                "httpOnly": False,
                "name": "lang",
                "path": "/",

                "secure": False,
                "session": True,
                "storeId": "0",
                "value": "en",
                "id": 14
            }
        ]
        #先进入页面
        driver.get("https://twitter.com/")
        #添加所有cookie
        for item in cookies:
            driver.add_cookie(item)
        #打开每个id的following页面
        driver.get('https://twitter.com/'+id+'/following')
        # 等待元素可见
        WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="react-root"]/div/div/div[2]/main/div/div/div/div[1]/div/section')))
        time.sleep(5)
        #载入所有页面

        while True:
            followingdata = driver.find_element(By.XPATH,
                                                '//*[@id="react-root"]/div/div/div[2]/main/div/div/div/div[1]/div/section').text
            # print(followingdata)
            following = re.findall(r'\n(@\.*?)\nFollow\w*?\n', followingdata)
            followingset.update(following)

            check_height = driver.execute_script("return document.body.scrollHeight;")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)
            newcheck_height = driver.execute_script("return document.body.scrollHeight;")
            if newcheck_height == check_height:
                break
        followinglist.extend(followingset)


        # followingdata=driver.find_element(By.XPATH,
        #                     '//*[@id="react-root"]/div/div/div[2]/main/div/div/div/div[1]/div/section').text
        # following = set(re.findall(r'\n(@\w+?)\n', followingdata))
        # print(following)
        # followinglist.extend(following)

        driver.close()
            #     break
            # except:
            #     time.sleep(10)
            #     continue
    #为该组的每个id创建线程
    while True:
        try:
            threadlist = []
            for name in loadtext['allgroup'][group]['idlist']:
                thread = threading.Thread(target=getfollowing, args=[name, ])
                thread.start()
                threadlist.append(thread)
            for t in threadlist:
                t.join()
            break
        except:
            continue
    # nowtimestamp=int(time.time())
    # for exf in range(len(loadtext['allgroup'][group]['timestamplist'])):
    #     if loadtext['allgroup'][group]['timestamplist'][0] < range(nowtimestamp-88200, nowtimestamp-86400):
    #         exfollowinglist = loadtext['allgroup'][group]['followinglist'][exf]
    #         break
    #     else:
    # exfollowinglist = loadtext['allgroup'][group]['followinglist'][0]
    # print(exfollowinglist)
    loadtext['allgroup'][group]['followinglistlist'].append(followinglist)
    loadtext['allgroup'][group]['timestamplist'].append(int(time.time()))

    # for i in loadtext['allgroup'][group]['followinglistlist']:
    print(len(loadtext['allgroup'][group]['followinglistlist']))


    # try:
    #     cofollowingset = reduce(lambda a, b: a & b, followinglist)
    # except:
    #     cofollowingset=set()
    #去掉原有的following
    print('follwoing1',len(followinglist))
    if len(loadtext['allgroup'][group]['followinglistlist'])>1:
        for ex in loadtext['allgroup'][group]['followinglistlist'][0]:
            try:
                followinglist.remove(ex)
            except:
                continue
    #计数新增following的个数
    # count=dict(Counter())
    # print(count)
    print('following2', len(followinglist))
    alertset = set()
    for i in range(len(followinglist)):
        num=followinglist.count(followinglist[i])
        print(i, followinglist[i],num)
        if num>1:#设置一个新增只通知一次
            alertset.add(followinglist[i])
    loadtext['allgroup'][group]['alertlist'].append(list(alertset))
    #     newco=list(cofollowingset - set(idzu['cofollowinglist']))
    # # newco.append('eeeee')
    # print(loadtext['allgroup'][idzu])
    # print(loadtext['allgroup'][idzu]['alertlist'])
    if alertset:
        webhook = DiscordWebhook(
            embeds=[{"author": {"name": 'yLitchan', "icon_url": "https://api.cyfan.top/acg", },
                     "title": group,
                     "description": str(alertset),# "fields": [{"name": "Value", "value": str(newco), "inline": True},
                     #                              {"name": "Txn Fee", "value": str(newco), "inline": True},
                     #                              {"name": "To", "value": str(newco), "inline": True},
                     #                              ],
                     "thumbnail": {"url": "https://api.cyfan.top/acg"},
                     "image": {"url": 'https://api.cyfan.top/acg'},
                     "footer": {"text": 'Galibur', "icon_url": "https://api.cyfan.top/acg", }, }],
            # content=str(newco),
            username='Spidey Bot',
            avatar_url='https://api.cyfan.top/acg', )
        webhook.api_post_request(url='https://discord.com/api/webhooks/1001134296972660816/cdIqGx2uw2Z3Rjk86c8jLHCU6Lmk1ZKtm3DKxSyivK64HfKaLbiXK8-f6F4po5tTxBAH')


while True:
    # try:
    tlist=[]
    for group in loadtext['allgroup']:
        thread=threading.Thread(target=getsfollowing,args=[group,])
        thread.start()
        tlist.append(thread)
    for t in tlist:
        t.join()
    #
    # except:
    #     continue
    #23h更新一次时间戳，预警列表，备份数据

    for j in loadtext['allgroup']:
        # if loadtext['allgroup'][alpha.json]['timestamplist'][-1] - loadtext['allgroup'][alpha.json]['timestamplist'][0] > 88200:
        for timenum in range(len(loadtext['allgroup'][j]['timestamplist'])):
            if loadtext['allgroup'][j]['timestamplist'][-1]-loadtext['allgroup'][j]['timestamplist'][timenum]> 88200:
                loadtext['allgroup'][j]['timestamplist'].remove(loadtext['allgroup'][j]['timestamplist'][timenum])
                loadtext['allgroup'][j]['followinglistlist'].remove(loadtext['allgroup'][j]['followinglistlist'][timenum])
                loadtext['allgroup'][j]['alertlist'].remove(loadtext['allgroup'][j]['alertlist'][timenum])
            else:
                break
    with open('twitterfollowing.json', 'w') as fpw:
        fpw.truncate()
        # fpw.seek(0)
        fpw.write(json.dumps(loadtext,indent=4))



