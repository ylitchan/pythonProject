import tkinter as tk
import tkinter.messagebox as messagebox
import threading
import tkinter.simpledialog
import selenium.webdriver.edge.service
from discord_webhook import DiscordWebhook
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from PIL import Image, ImageTk
import random
import time
from selenium.webdriver.common.keys import Keys
import requests as req

event = threading.Event()


class GUI():
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('钱包追踪')
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

    # def sendmsg(self,chanel,id,pw):
    #     """按钮事件，一直循环"""
    #     def login():
    #         driver.get('https://discord.com/login?redirect_to=%2Fchannels%2F920254345562439751%2F'+chanel)
    #
    #         name = driver.find_element(By.XPATH,
    #                                    '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[1]/div/div[2]/input')
    #         password = driver.find_element(By.XPATH,
    #                                        '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[2]/div/input')
    #         name.send_keys(id)
    #         password.send_keys(pw)
    #         driver.find_element(By.XPATH,
    #                             '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/button[2]').click()
    #     while True:
    #         event.wait()
    #         try:
    #             driver = webdriver.Edge(options=self.options, service=self.service)
    #             a = random.randint(1, 67)
    #             driver.get('https://www.juzikong.com/tags/%E4%BC%A4%E6%84%9F?page=' + str(a))
    #             textlist = driver.find_elements(By.CLASS_NAME, 'content_2hYZM')
    #             textset = set()
    #             for i in textlist:
    #                 textset.add(i.text)
    #             login()
    #             while True:
    #                 try:
    #                     time.sleep(10)
    #                     n = 0
    #                     for i in textset:
    #                         if n == 0:
    #                             try:
    #                                 text = driver.find_element(By.XPATH,'//*[@id="app-mount"]/div[2]/div/div[1]/div/div[2]/div/div[1]/div/div/div[2]/div[2]/main/form/div[1]/div/div/div[2]/div/div[3]/div/div[2]/div')
    #                             except:
    #                                 text = driver.find_element(By.XPATH, '//*[@id="app-mount"]/div[2]/div/div[1]/div/div[2]/div/div[1]/div/div/div[3]/div[2]/main/form/div[1]/div/div/div[1]/div/div[3]/div/div[2]/div')
    #                             text.send_keys(i)
    #                             # print(text)
    #                             text.send_keys(Keys.ENTER)
    #                             n += 1
    #
    #                         else:
    #                             break
    #                     self.w1.insert(1.0, chanel+'频道正常\n')
    #                         # if 'reactionMe-1PwQAc' not in text:
    #                         #     buttonlist[-1].click()
    #
    #                         # else:
    #                         #     tada[-1] = text
    #                         #     with open('tada.json', 'w') as fp:
    #                         #         fp.write(json.dumps(tada))
    #                 except:
    #                     driver.close()
    #                     login()
    #                     continue
    #                 time.sleep(21600)
    #         except:
    #             continue
    def login(self,driver,channel,id,pw):
        driver.get('https://discord.com/login?redirect_to=%2Fchannels%2F'+ channel)

        name = driver.find_element(By.XPATH,
                                   '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[1]/div/div[2]/input')
        password = driver.find_element(By.XPATH,
                                       '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[2]/div/input')
        name.send_keys(id)
        password.send_keys(pw)
        driver.find_element(By.XPATH,
                            '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/button[2]').click()
    def sendmsgs(self,channel,id,pw,st,content):

        while True:
            event.wait()
            try:
                driver = webdriver.Edge(options=self.options, service=self.service)
                self.login(driver,channel,id,pw)
                time.sleep(10)
                while True:
                    try:
                        # try:
                        #     text = driver.find_element(By.XPATH,'//*[@id="app-mount"]/div[2]/div/div[1]/div/div[2]/div/div[1]/div/div/div[2]/div[2]/main/form/div[1]/div/div/div[2]/div/div[3]/div/div[2]/div')
                        # except:
                        #     text = driver.find_element(By.XPATH, '//*[@id="app-mount"]/div[2]/div/div[1]/div/div[2]/div/div[1]/div/div/div[3]/div[2]/main/form/div[1]/div/div/div[1]/div/div[3]/div/div[2]/div')
                        text = driver.find_element(By.CLASS_NAME, 'editor-H2NA06')
                        text.send_keys(content)
                        time.sleep(2)
                        text.send_keys(Keys.ENTER)
                        # time.sleep(9999)
                        # try:


                        text.send_keys(Keys.ENTER)

                        # except:
                        #     pass
                        self.w1.insert(1.0, channel+'频道正常\n')
                    except:
                        driver.close()
                        self.login(driver,channel,id,pw)
                        continue
                    time.sleep(st)
            except:
                continue
            # except:
            #     continue


    def autotada(self,channel,id,pw,st):
        # def login():
        #     driver.get('https://discord.com/login?redirect_to=%2Fchannels%2F984569745447727124%2F994535100266070036')
        #
        #     name = driver.find_element(By.XPATH,
        #                                '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[1]/div/div[2]/input')
        #     password = driver.find_element(By.XPATH,
        #                                    '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[2]/div/input')
        #     name.send_keys(id)
        #     password.send_keys(pw)
        #     driver.find_element(By.XPATH,
        #                         '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/button[2]').click()
        while True:
            event.wait()
            try:
                driver = webdriver.Edge(options=self.options, service=self.service)
                self.login(driver,channel,id,pw)
                while True:
                    try:
                        time.sleep(st)
                        buttonlist = driver.find_elements(By.CLASS_NAME, 'reaction-3vwAF2')
                        text = buttonlist[-1].get_attribute('class')
                        if 'reactionMe-1PwQAc' not in text:
                            buttonlist[-1].click()
                        self.w1.insert(1.0, channel+text + '自动抽奖正常\n')
                    except:
                        driver.close()
                        self.login(driver,channel,id,pw)
                        continue
            except:
                continue

    def tadaalert(self,channel,id,pw,st):
        # def login():
        #     driver.get('https://discord.com/login?redirect_to=%2Fchannels%2F984569745447727124%2F994535100266070036')
        #
        #     name = driver.find_element(By.XPATH,
        #                                '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[1]/div/div[2]/input')
        #     password = driver.find_element(By.XPATH,
        #                                    '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[2]/div/input')
        #     name.send_keys(id)
        #     password.send_keys(pw)
        #     driver.find_element(By.XPATH,
        #                         '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/button[2]').click()
        while True:
            event.wait()
            try:
                driver = webdriver.Edge(options=self.options, service=self.service)
                self.login(driver,channel,id,pw)
                while True:
                    try:
                        time.sleep(st)
                        textlist = driver.find_elements(By.CLASS_NAME, 'message-2CShn3')
                        text = textlist[-1].text
                        if 'GiveawayBot' not in text and text not in self.msglist:
                            data={
                                "token": "9c7cdf925dfb4c4aa05f25ef0ecac725",
                                "title": "tada",
                                "content": text,
                                "topic": "1",
                                "template": "html"
                            }
                            data=json.dumps(data).encode(encoding='utf-8')
                            req.post(url='http://www.pushplus.plus/send/',data=data)
                            self.msglist[-1]=text
                        self.w1.insert(1.0, channel + '抽奖提醒正常\n')
                    except:
                        driver.close()
                        self.login(driver,channel,id,pw)
                        continue
            except:
                continue
    def start(self):
        event.set()
        id = tkinter.simpledialog.askstring(title="dc",prompt="ID:")
        pw = tkinter.simpledialog.askstring(title="pw",prompt="password:")
        #readon的两个频道，6h
        for i in ['920254345562439751%2F989777348205379624', '920254345562439751%2F943520679045775380']:
            driver = webdriver.Edge(options=self.options, service=self.service)
            a = random.randint(1, 67)
            driver.get('https://www.juzikong.com/tags/%E4%BC%A4%E6%84%9F?page=' + str(a))
            content = driver.find_elements(By.CLASS_NAME, 'content_2hYZM')[random.randint(0,14)].text.replace('\n','')
            driver.close()
            thread = threading.Thread(target=self.sendmsgs, args=[i,id,pw,21600,content])
            thread.daemon = True
            thread.start()
        #币安的频道
        thread = threading.Thread(target=self.sendmsgs, args=['898153438217633862%2F899598848102637589',id,pw,3600,'/work'])
        thread.daemon = True
        thread.start()
        thread = threading.Thread(target=self.sendmsgs,
                                  args=['898153438217633862%2F899598848102637589', id, pw, 86400, '/daily'])
        thread.daemon = True
        thread.start()
        #币安的抽奖
        thread = threading.Thread(target=self.tadaalert, args=['898153438217633862%2F968000068726718494',id, pw,10])
        thread.daemon = True
        thread.start()
        messagebox.showinfo(title='提示', message='开启')

    def end(self):
        event.clear()
        webdriver.Edge(options=self.options, service=self.service).quit()
        messagebox.showinfo(title='提示', message='结束')


if __name__ == '__main__':
    a = GUI()
    a.root.mainloop()
