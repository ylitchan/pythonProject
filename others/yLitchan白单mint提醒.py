# 创作人:颜立全
import re
import tkinter as tk
import tkinter.messagebox as messagebox
import threading
import tkinter.simpledialog
import selenium.webdriver.edge.service
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from PIL import Image, ImageTk
import random
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import datetime
import time
from selenium.webdriver.common.keys import Keys
import requests as req
from discord_webhook import DiscordWebhook
options = webdriver.EdgeOptions()
options.headless = True
driver=webdriver.Edge(options=options)
driver.get('https://discord.com/login?redirect_to=%2Fchannels%2F1001132842094432407%2F1025743598622363688')
name = driver.find_element(By.XPATH,
                           '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[1]/div/div[2]/input')
password = driver.find_element(By.XPATH,
                               '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[2]/div/input')
name.send_keys('898475174@qq.com')
password.send_keys('yanlq2016')
driver.find_element(By.XPATH,'//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/button[2]').click()
WebDriverWait(driver, 60, 0.5).until(
            EC.visibility_of_element_located((By.CLASS_NAME, 'heading-md-medium-2DVCeJ')),
            message='超时啦!')
driver.find_element(By.CLASS_NAME, 'closedFolderIconWrapper-3tRb2d').click()
monlist=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
nowmday=[0]
donechannel=set()
data = {
                        "token": "e73179f25ade41729eae654a2decec15",
                        "title": datetime.datetime.now().strftime('%H:%M:%S'),
                        "content": 'on',
                        "topic": "1",
                        "template": "html"
                    }
data = json.dumps(data).encode(encoding='utf-8')
req.post(url='http://www.pushplus.plus/send/', data=data)
while True:
    mday = datetime.datetime.now().timetuple().tm_mday
    print(mday)
    mon = datetime.datetime.now().timetuple().tm_mon
    channelset = set()
    channels = set()
    ele = driver.find_element(By.ID, 'folder-items-2852193276').get_attribute("innerHTML")
    for i in re.findall(r'/(\d+?)/', ele):
        channels.add('https://discord.com/channels/' + i)
    if mday != nowmday[-1]:
        donechannel.clear()
    channelset.update(channels.difference(donechannel))
    donechannel.update(channels)
    for i in channelset:
        try:
            # date = []
            alert = [0]
            month=[0]
            price=[]
            ActionChains(driver).key_down(Keys.CONTROL).send_keys('k').key_up(Keys.CONTROL).send_keys(i).perform()
            time.sleep(2)
            ActionChains(driver).send_keys(Keys.ENTER).perform()
            WebDriverWait(driver, 60, 0.5).until(
                EC.visibility_of_element_located((By.CLASS_NAME, 'channelName-3KPsGw')),
                message='超时啦!')
            for j in driver.find_elements(By.CLASS_NAME,'channelName-3KPsGw'):
                try:
                    if re.findall(r'mint|date|day|sale|price|cost|free|time',j.text,re.I):
                        price.append(j.text)
                        for i in range(0,12):
                            if re.findall(monlist[i],j.text,re.I):
                                month.append(i+1)
                                alert.append(int(re.findall(r'\d+', j.text, re.I)[0]))
                                # date.append(alpha.json.text)
                                break
                            elif i==11 and '/' in j.text:
                                month.append(int(re.findall(r'\d+', j.text, re.I)[0]))
                                alert.append(int(re.findall(r'\d+', j.text, re.I)[1]))
                                # date.append(alpha.json.text)
                        # else:# re.findall(r'price|cost|free', alpha.json.text, re.I):
                        #     price.append(alpha.json.text)
                except:
                    continue
            for l in range(0,len(month)):
                if mday - alert[l] in (0,-1) and month[l]==mon:
                    if mday - alert[l]==-1:
                        djs='明天'
                    elif mday - alert[l]==0:
                        djs='今天'
                    print('yes')
                    pjname = driver.find_element(By.CLASS_NAME, 'name-3Uvkvr').text
                    headers = {
                        'Authorization': 'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxNzg4MDM1NjQ4MSJ9.pFKEyy_0kBT1WKMy7sGnbBjEORtTKI6u0RGoH-R5pCiHZ5CBFG1s4TD80YYPezi4HLW4jTQ2niUH_fRJWCeqEw',
                        'Content-Type': 'application/json'
                    }
                    data = {
                        "wId": "26300c59-da79-419b-8d43-92714673b23c",
                        "wcId": "48628454627@chatroom",
                        "content": pjname+djs+'mint\n'  + str(price)
                    }
                    data = json.dumps(data).encode(encoding='utf-8')
                    req.post(url='http://114.107.252.79:9899/sendText', data=data, headers=headers)
                    data = {
                        "token": "e73179f25ade41729eae654a2decec15",
                        "title": pjname,
                        "content": djs+'mint\n'  + str(price),
                        "topic": "1",
                        "template": "html"
                    }
                    data = json.dumps(data).encode(encoding='utf-8')
                    req.post(url='http://www.pushplus.plus/send/', data=data)
                    webhook = DiscordWebhook(
                        embeds=[{"author": {"name": 'mint 提醒', "icon_url": "https://api.cyfan.top/acg", },
                                 "title": pjname,
                                 "description":str(price),
                                 "thumbnail": {"url": "https://api.cyfan.top/acg"},
                                 "image": {"url": 'https://api.cyfan.top/acg'},
                                 "footer": {"text": 'yLitchan', "icon_url": " ", }, }],
                        content=pjname+djs+'mint',
                        username='Spidey Bot',
                        avatar_url='https://api.cyfan.top/acg', )
                    webhook.api_post_request(
                        url='https://discord.com/api/webhooks/1028331538275909683/2MpNZekZ0VmBtWqE6-Fc7fnBDccEp4CcMcgwvJmlZz3-2pUmgsgJleUKejm__HDLMhlS')
        except:
            continue
    nowmday[-1] = datetime.datetime.now().timetuple().tm_mday
    print(datetime.datetime.now().strftime('%H:%M:%S'),nowmday)
    time.sleep(10800)





