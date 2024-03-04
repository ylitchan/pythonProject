# 创作人:颜立全
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
driver=webdriver.Edge()
driver.get('https://item.jd.com/100038004375.html#crumb-wrap')
time.sleep(30)
while True:
    try:
        driver.refresh()
        btn=driver.find_element(By.CLASS_NAME,'btn-special1')
        if btn.text=='抢购':
            btn.click()
    except:
        continue

