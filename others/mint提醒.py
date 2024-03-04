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
driver=webdriver.Edge()
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


while True:
    pj = ['']
    channelset = set()
    ele = driver.find_element(By.ID, 'folder-items-2852193276').get_attribute("innerHTML")
    for i in re.findall(r'/(\d+?)/', ele):
        channelset.add('https://discord.com/channels/' + i)
    print(channelset)

    for i in channelset:
        alert = ['']
        name=['']
        ActionChains(driver).key_down(Keys.CONTROL).send_keys('k').key_up(Keys.CONTROL).send_keys(i).perform()
        time.sleep(2)
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        WebDriverWait(driver, 60, 0.5).until(
            EC.visibility_of_element_located((By.CLASS_NAME, 'channelName-3KPsGw')),
            message='超时啦!')
        pjname = driver.find_element(By.CLASS_NAME, 'name-3Uvkvr').text
        for j in driver.find_elements(By.CLASS_NAME,'channelName-3KPsGw'):
            if (re.findall(r'\bmint\b',j.text,re.I) or re.findall(r'\bprice\b',j.text,re.I)) and re.findall(r'\d+',j.text,re.I):
                name[-1]=pjname+'\n'
                alert[-1] += j.text + '\n'

        pj[-1]+=name[-1]+alert[-1]
    print(pj)

    data = {
        "token": "87a24d543dda4c0ba2b97540948632c2",
        "title": 'wl提醒',
        "content": pj[-1],
        "topic": "1",
        "template": "html"
    }
    data = json.dumps(data).encode(encoding='utf-8')
    req.post(url='http://www.pushplus.plus/send/', data=data)
    time.sleep(43200)


