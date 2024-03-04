# 创作人:颜立全
import re
import requests as req
import threading
import selenium.webdriver.edge.service
from discord_webhook import DiscordWebhook
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from flask import Flask, redirect, url_for, request, render_template
from decimal import Decimal
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time
options = webdriver.EdgeOptions()
options.headless = True
service = webdriver.edge.service.Service()  # executable_path="D:/msedgedriver.exe"
driver=webdriver.Edge(options=options,service=service)
driver.get('https://discord.com/login?redirect_to=%2Fchannels%2F984569745447727124%2F994535100266070036')
name = driver.find_element(By.XPATH,'//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[1]/div/div[2]/input')
password = driver.find_element(By.XPATH,'//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[2]/div/input')
name.send_keys('898475174@qq.com')
password.send_keys('yanlq2016')
driver.find_element(By.XPATH,'//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/button[2]').click()
time.sleep(10)
while True:
    try:
        buttonlist = driver.find_elements(By.CLASS_NAME,'reaction-3vwAF2')
        text=buttonlist[-1].get_attribute('class')
        print(text)
        if 'reactionMe-1PwQAc' not in text:
            buttonlist[-1].click()
        time.sleep(10)
    except:
        continue

