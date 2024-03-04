# 创作人:颜立全
import random
import re
import requests as req
import threading
import selenium.webdriver.edge.service
import json
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from flask import Flask, redirect, url_for, request, render_template
from decimal import Decimal
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time

options = webdriver.EdgeOptions()
service = webdriver.edge.service.Service(
    executable_path=r"D:\allProjects\pyDemo\msedgedriver.exe")  # executable_path="D:/msedgedriver.exe"
heads = ['user-agent=Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) '
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
# fp = open('twitterfollowing.json', 'r+')
# 读取本地文件，载入内存
# loadtext=json.loads(fp.read())
# 该函数为每个组更新数据
# def getsfollowing(group):# ,"yLitchan"
#     followinglist = []  #存储每个组
# 的所有following
# 该函数为每个组的每个id获取following
# def getfollowing(id):
#     followingset=set()
options.add_argument(random.choice(heads))
# options.add_argument(r'C:\Users\颜立全\AppData\Local\Microsoft\Edge\User Data\Default')
driver = webdriver.Edge(options=options, service=service)
driver.get('https://discord.com/channels/1001132842094432407/1036569767236083712')
time.sleep(9999)
# name = driver.find_element(By.XPATH, '//*[@id="uid_5"]')
# password = driver.find_element(By.XPATH, '//*[@id="uid_7"]')
# name.send_keys('898475174@qq.com')
# password.send_keys('yanlq2016')
# driver.find_element(By.XPATH,
#                     '//*[@id="app-mount"]/div[2]/div[1]/div[1]/div/div/div/form/div[2]/div/div[1]/div[2]/button[2]').click()
# time.sleep(10)
while True:
    try:
        buttonlist = driver.find_element(By.XPATH,
                                         '//*[@id="app-mount"]/div[2]/div[1]/div[1]/div/div[2]/div/div/div/div/div[2]/div[2]/main/form/div/div[1]/div/textarea')
        for i in '/work':
            buttonlist.send_keys(i)
            time.sleep(0.5)
        time.sleep(3)
        ActionChains(driver).send_keys(Keys.ENTER).send_keys(Keys.ENTER)
        time.sleep(30)
    except:
        continue
