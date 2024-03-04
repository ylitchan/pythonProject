# 创作人:颜立全
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
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
import time
from selenium.webdriver.common.keys import Keys
import requests as req
import datetime

event = threading.Event()


class GUI():
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('angrycat')
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
        self.Button0.place(x=11, y=270, width=100, height=30)
        self.Button0 = tk.Button(self.root, text="add", command=self.add)
        self.Button0.place(x=122, y=270, width=100, height=30)
        self.Button0 = tk.Button(self.root, text="end", command=self.end)
        self.Button0.place(x=233, y=270, width=100, height=30)
        self.w1 = tk.Text(self.root)
        self.w1.place(x=11, y=150, width=333, height=100)
        self.root.bind('<Control-d>', self.draw)

    def draw(self, event):
        a.root.withdraw()


    def login(self,driver,channel,id,pw):
        driver.get('https://discord.com/login?redirect_to=%2Fchannels%2F'+ channel.replace('/','%2F'))

        name = driver.find_element(By.XPATH,
                                   '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[1]/div/div[2]/input')
        password = driver.find_element(By.XPATH,
                                       '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[2]/div/input')
        name.send_keys(id)
        password.send_keys(pw)
        driver.find_element(By.XPATH,
                            '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/button[2]').click()
    def sendmsgs(self,channel,id,pw):
        driver = webdriver.Edge(options=self.options, service=self.service)
        self.login(driver, channel, id, pw)
        WebDriverWait(driver, 10, 0.5).until(
            EC.visibility_of_element_located((By.CLASS_NAME, 'label-31sIdr')),
            message='超时啦!')
        while True:
            event.wait()
            try:

                driver.find_element(By.CLASS_NAME,'label-31sIdr').click()
                time.sleep(5)
            except:
                continue
            self.w1.insert(1.0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %f")+ '正常\n')

    def goon(self):
        channel = tkinter.simpledialog.askstring(title="channel", prompt="channel:")
        if channel:
            thread = threading.Thread(target=self.sendmsgs,
                                      args=[channel, self.id, self.pw])
            thread.daemon = True
            thread.start()
        messagebox.showinfo(title='提示', message='开启')

    def start(self):
        event.set()

        self.id = tkinter.simpledialog.askstring(title="dc",prompt="ID:")
        self.pw = tkinter.simpledialog.askstring(title="pw",prompt="password:")
        self.goon()


    def add(self):
        self.goon()



    def end(self):
        event.clear()
        webdriver.Edge(options=self.options, service=self.service).quit()
        messagebox.showinfo(title='提示', message='结束')


if __name__ == '__main__':
    a = GUI()
    a.root.mainloop()


