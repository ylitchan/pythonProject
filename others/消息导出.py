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

event = threading.Event()


class GUI():
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('消息导出')
        self.root.geometry("355x300+300+150")
        self.root.resizable(0, 0)
        self.interface()
        self.options = webdriver.EdgeOptions()
        # self.options.headless = True
        self.service = webdriver.edge.service.Service(executable_path="msedgedriver.exe")
        self.msglist=['']


    def get_img(self, filename, width, height):
        self.im = Image.open(filename).resize((width, height))
        self.im = ImageTk.PhotoImage(self.im)
        return self.im

    def interface(self):
        """"界面编写位置"""
        self.canvas = tk.Canvas(self.root, width=355, height=300, bd=0, highlightthickness=0)
        self.im_root = self.get_img('acg.jpeg', 355, 300)
        self.canvas.create_image(178, 150, image=self.im_root)
        self.canvas.pack(side='top')
        self.Button0 = tk.Button(self.root, text="login", command=self.start)
        self.Button0.place(x=77, y=270, width=100, height=30)
        self.Button0 = tk.Button(self.root, text="end", command=self.end)
        self.Button0.place(x=178, y=270, width=100, height=30)
        self.w1 = tk.Text(self.root)
        self.w1.place(x=11, y=150, width=333, height=100)
        self.root.bind('<Control-d>', self.draw)

    def draw(self, event):
        a.root.withdraw()


    def login(self,driver,channel):
        driver.get('https://discord.com/login?redirect_to=%2Fchannels%2F'+ channel.replace('/','%2F'))

        name = driver.find_element(By.XPATH,
                                   '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[1]/div/div[2]/input')
        password = driver.find_element(By.XPATH,
                                       '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[2]/div/input')
        name.send_keys('898475174@qq.com')
        password.send_keys('yanlq2016')
        driver.find_element(By.XPATH,
                            '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/button[2]').click()
    def getmsgs(self,channel):
        driver = webdriver.Edge(options=self.options, service=self.service)
        self.login(driver, channel)
        WebDriverWait(driver, 600, 0.5).until(
            EC.visibility_of_element_located((By.CLASS_NAME, 'editor-H2NA06')),
            message='超时啦!')
        n=0
        msglist=[]
        time.sleep(60)

        while True:
            event.wait()
            try:
                msgs=driver.find_elements(By.CLASS_NAME, 'messageContent-2t3eCI')
                for i in msgs:
                    if i.text not in msglist and '@' not in i.text and 'おはよう' not in i.text and 'こんばん' not in i.text:
                        msglist.append(i.text)
                        self.w1.insert(1.0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %f") + '第' + str(
                            n) + '次' + i.text + '\n')
                        n += 1
                ActionChains(driver).key_down(Keys.PAGE_DOWN).perform()
            except:
                continue
                # time.sleep(5)
                # ActionChains(driver).key_up(Keys.PAGE_DOWN).perform()
                # time.sleep(2)


    def start(self):
        event.set()
        #币安的频道
        thread = threading.Thread(target=self.getmsgs, args=['917650164737536031/928234081664249886'])
        thread.daemon = True
        thread.start()


    def end(self):
        event.clear()
        webdriver.Edge(options=self.options, service=self.service).quit()
        messagebox.showinfo(title='提示', message='结束')


if __name__ == '__main__':
    a = GUI()
    a.root.mainloop()



