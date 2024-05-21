# 创作人:颜立全
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

driver = webdriver.Edge()
driver.get('https://item.jd.com/100038004375.html#crumb-wrap')
time.sleep(30)
while True:
    try:
        driver.refresh()
        btn = driver.find_element(By.CLASS_NAME, 'btn-special1')
        if btn.text == '抢购':
            btn.click()
    except:
        continue
