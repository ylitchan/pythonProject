# 创作人:颜立全
import tkinter as tk
import tkinter.messagebox as messagebox
import threading
import tkinter.simpledialog
import selenium.webdriver.edge.service
from selenium import webdriver
from selenium.webdriver.common.by import By
from PIL import Image, ImageTk
import time
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import datetime
import requests as req
import json
from discord_webhook import DiscordWebhook

event = threading.Event()


class GUI():
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('fitr价格预警')
        self.root.geometry("355x300+300+150")
        self.root.resizable(0, 0)
        self.interface()
        self.options = webdriver.EdgeOptions()
        self.options.headless = True
        # self.options.add_argument(r'--user-data-dir=D:\PycharmProjects\demos\User Data')
        self.service = webdriver.edge.service.Service(executable_path="msedgedriver.exe")
        self.driver=webdriver.Edge(options=self.options)
        self.hashlist = ['']



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

    def fitralert(self,sale):
        self.driver.get('https://tofunft.com/zh-CN/collection/fitr-gym-bags/items?sort=price_asc')
        while True:
            event.wait()
            try:
                price = self.driver.find_element(By.XPATH,'//*[@id="__next"]/div[2]/div[1]/div[5]/div[2]/div[1]/div[1]/div[2]/div[2]/div/p').text
                price = price.replace(' BNB', '')
                print(price)
                hash = self.driver.find_element(By.XPATH,'//*[@id="__next"]/div[2]/div[1]/div[5]/div[2]/div[1]/div[1]/div[2]/div[2]/a').get_attribute('href')
                if sale >= float(price) and hash not in self.hashlist:
                    self.hashlist[-1] = hash
                    print(hash)
                    self.w1.insert(1.0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %f") +'\n'+ price+'\n')
                    webhook = DiscordWebhook(
                        embeds=[{"author": {"name": 'yLitchan', "icon_url": "https://api.cyfan.top/acg", },
                                 "title":'fitr',
                                 "description": price,
                                 # "fields": [{"name": "Value", "value": str(newco), "inline": True},
                                 #                              {"name": "Txn Fee", "value": str(newco), "inline": True},
                                 #                              {"name": "To", "value": str(newco), "inline": True},
                                 #                              ],
                                 "thumbnail": {"url": "https://api.cyfan.top/acg"},
                                 "image": {"url": 'https://api.cyfan.top/acg'},
                                 "footer": {"text": 'Galibur', "icon_url": "https://api.cyfan.top/acg", }, }],
                        # content=str(newco),
                        username='Spidey Bot',
                        avatar_url='https://api.cyfan.top/acg', )
                    webhook.api_post_request(
                        url='https://discord.com/api/webhooks/1001134296972660816/cdIqGx2uw2Z3Rjk86c8jLHCU6Lmk1ZKtm3DKxSyivK64HfKaLbiXK8-f6F4po5tTxBAH')
            except:
                continue
    def start(self):
        event.set()
        sale=tkinter.simpledialog.askfloat(title="fitr",prompt="预警价:")
        thread=threading.Thread(target=self.fitralert, args=[sale,])
        thread.daemon = True
        thread.start()
        messagebox.showinfo(title='提示', message='开启')

    def end(self):
        event.clear()
        self.driver.quit()
        messagebox.showinfo(title='提示', message='结束')


if __name__ == '__main__':
    a = GUI()
    a.root.mainloop()












