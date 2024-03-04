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
driver.get('https://discord.com/login?redirect_to=%2Fchannels%2F1001132842094432407%2F1001376763710033920')
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
commandlist=['']
n=0
while True:
    ActionChains(driver).key_down(Keys.CONTROL).send_keys('k').key_up(Keys.CONTROL).send_keys(
        'https://discord.com/channels/898153438217633862/949271940428861440').send_keys(Keys.ENTER).perform()
    WebDriverWait(driver, 60, 0.5).until(
        EC.visibility_of_element_located((By.CLASS_NAME, 'messageListItem-ZZ7v6g')),
        message='超时啦!')
    ActionChains(driver).send_keys(':bnbDCoin:').perform()
    ActionChains(driver).send_keys(Keys.ENTER).perform()
    ActionChains(driver).key_down(Keys.CONTROL).send_keys('k').key_up(Keys.CONTROL).send_keys(
        'https://discord.com/channels/898153438217633862/918711890232873000').send_keys(Keys.ENTER).perform()
    WebDriverWait(driver, 60, 0.5).until(
        EC.visibility_of_element_located((By.CLASS_NAME, 'messageListItem-ZZ7v6g')),
        message='超时啦!')
    ActionChains(driver).send_keys(':bnbDCoin:').perform()
    ActionChains(driver).send_keys(Keys.ENTER).perform()
    ActionChains(driver).key_down(Keys.CONTROL).send_keys('k').key_up(Keys.CONTROL).send_keys(
        'https://discord.com/channels/898153438217633862/962932744101429308').send_keys(Keys.ENTER).perform()
    WebDriverWait(driver, 60, 0.5).until(
        EC.visibility_of_element_located((By.CLASS_NAME, 'messageListItem-ZZ7v6g')),
        message='超时啦!')
    ActionChains(driver).send_keys('/work').perform()
    time.sleep(2)
    ActionChains(driver).send_keys(Keys.ENTER).perform()
    time.sleep(2)
    ActionChains(driver).send_keys(Keys.ENTER).perform()
    time.sleep(2)
    for i in range(0,5):
        ActionChains(driver).send_keys(Keys.BACKSPACE).perform()

    if n ==11:
        ActionChains(driver).send_keys('/daily').perform()
        time.sleep(2)
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(2)
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(2)
        for i in range(0, 6):
            ActionChains(driver).send_keys(Keys.BACKSPACE).perform()
        n = 0

    elif n % 3==0:
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
                date = ['']
                alert = [0]
                month=[0]
                price=['']
                ActionChains(driver).key_down(Keys.CONTROL).send_keys('k').key_up(Keys.CONTROL).send_keys(i).perform()
                time.sleep(2)
                ActionChains(driver).send_keys(Keys.ENTER).perform()
                WebDriverWait(driver, 60, 0.5).until(
                    EC.visibility_of_element_located((By.CLASS_NAME, 'channelName-3KPsGw')),
                    message='超时啦!')
                for j in driver.find_elements(By.CLASS_NAME,'channelName-3KPsGw'):
                    try:
                        if re.findall(r'\bmint\b',j.text,re.I) and not re.findall(r'price|cost',j.text,re.I) and re.findall(r'\d+',j.text,re.I):
                            for i in range(0,12):
                                if re.findall(monlist[i],j.text,re.I):
                                    month[-1]=i+1
                                    alert[-1] = int(re.findall(r'\d+', j.text, re.I)[0])
                                    date[-1] = j.text
                                    break
                                elif i==11 and '/' in j.text:
                                    month[-1] = int(re.findall(r'\d+', j.text, re.I)[0])
                                    alert[-1] = int(re.findall(r'\d+', j.text, re.I)[1])
                                    date[-1] = j.text
                        elif re.findall(r'price|cost', j.text, re.I):
                            price[-1]=j.text
                    except:
                        continue

                if mday - alert[-1] in (0,-1) and month[-1]==mon:
                    if mday - alert[-1]==-1:
                        djs='明天'
                    elif mday - alert[-1]==0:
                        djs='今天'
                    print('yes')
                    pjname = driver.find_element(By.CLASS_NAME, 'name-3Uvkvr').text
                    data = {
                        "token": "e73179f25ade41729eae654a2decec15",
                        "title": pjname,
                        "content": djs+'mint\ny:' + date[-1] +'\n' + price[-1],
                        "topic": "1",
                        "template": "html"
                    }
                    data = json.dumps(data).encode(encoding='utf-8')
                    req.post(url='http://www.pushplus.plus/send/', data=data)
                    webhook = DiscordWebhook(
                        embeds=[{"author": {"name": 'mint 提醒', "icon_url": "https://api.cyfan.top/acg", },
                                 "title": pjname,
                                 "description":date[-1]+'\n'+price[-1],
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
        print(nowmday)
        n+=1
    else:
        oldtime = time.time()
        ActionChains(driver).key_down(Keys.CONTROL).send_keys('k').key_up(Keys.CONTROL).send_keys(
            'https://discord.com/channels/898153438217633862/968000068726718494').send_keys(Keys.ENTER).perform()
        WebDriverWait(driver, 60, 0.5).until(
            EC.visibility_of_element_located((By.CLASS_NAME, 'messageListItem-ZZ7v6g')),
            message='超时啦!')
        while time.time()-oldtime<=3600:
            command=driver.find_elements(By.CLASS_NAME,'messageListItem-ZZ7v6g')[-1].text
            if re.findall(r'/giveaway create', command) and command != commandlist[-1]:
                commandlist[-1] = command
                data = {
                    "token": "e73179f25ade41729eae654a2decec15",
                    "title": '币安AMA抽奖',
                    "content": command,
                    "topic": "1",
                    "template": "html"
                }
                data = json.dumps(data).encode(encoding='utf-8')
                req.post(url='http://www.pushplus.plus/send/', data=data)
        n += 1
    print(datetime.datetime.now().strftime('%H:%M:%S'),n)





