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
        self.options.add_argument(
            "user-agent=Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/103.0.5060.134 Mobile Safari/537.36 Edg/103.0.1264.71")
        self.driver = webdriver.Edge(options=self.options, service=self.service)

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
        self.Button0 = tk.Button(self.root, text="启动追踪", command=self.start)
        self.Button0.place(x=11, y=270, width=100, height=30)
        self.Button0 = tk.Button(self.root, text="增加钱包", command=self.addqb)
        self.Button0.place(x=122, y=270, width=100, height=30)
        self.Button0 = tk.Button(self.root, text="继续追踪", command=self.conti)
        self.Button0.place(x=233, y=270, width=100, height=30)
        self.root.bind('<Control-d>', self.draw)

    def draw(self, event):
        a.root.withdraw()

    def event(self):
        """按钮事件，一直循环"""

        with open('nftbot.json', 'r+', encoding='utf-8') as fp:
            while True:
                event.wait()
                self.loadtext = json.load(fp)
                self.hashlist = []
                for i in self.loadtext['urldict']:
                    try:
                        self.driver.get(self.loadtext['urldict'][i])
                        a = self.driver.find_element(By.XPATH,
                                                     '/html/body/div[1]/main/div[4]/div[3]/div[2]/div/div[1]/div['
                                                     '2]/table/tbody/tr[1]/td[2]').text
                        if a not in self.loadtext['nfthash']:
                            b = self.driver.find_element(By.XPATH,
                                                         '//*[@id="transactions"]/div[2]/table/tbody/tr[1]/td[3]/span').text
                            c = self.driver.find_element(By.XPATH,
                                                         '//*[@id="transactions"]/div[2]/table/tbody/tr[1]/td[9]').text
                            d = self.driver.find_element(By.XPATH,
                                                         '//*[@id="transactions"]/div[2]/table/tbody/tr[1]/td[10]').text
                            e = self.driver.find_element(By.XPATH,
                                                         '//*[@id="transactions"]/div[2]/table/tbody/tr[1]/td[11]/span').text
                            f = self.driver.find_element(By.XPATH,
                                                         '//*[@id="transactions"]/div[2]/table/tbody/tr[1]/td[2]/a').get_attribute(
                                'href')
                            try:
                                self.driver.get(f)
                                g = self.driver.find_element(By.XPATH,
                                                             '//*[@id="wrapperContent"]/li[1]/div[1]/div[2]/a').text
                            except:
                                g = '无'
                                pass
                            self.webhook = DiscordWebhook(
                                embeds=[{"author": {"name": i, "icon_url": "https://api.cyfan.top/acg", },
                                         "title": 'method',
                                         "description": b, "fields": [{"name": "Value", "value": d, "inline": True},
                                                                      {"name": "Txn Fee", "value": e, "inline": True},
                                                                      {"name": "To", "value": c, "inline": True},
                                                                      ],
                                         "thumbnail": {"url": "https://api.cyfan.top/acg"},
                                         "image": {"url": 'https://api.cyfan.top/acg'},
                                         "footer": {"text": g, "icon_url": " ", }, }],
                                content=self.loadtext['urldict'][i],
                                username='Spidey Bot',
                                avatar_url='https://api.cyfan.top/acg', )
                            self.webhook.api_post_request(url='https://discord.com/api/webhooks/1001134296972660816/cdIqGx2uw2Z3Rjk86c8jLHCU6Lmk1ZKtm3DKxSyivK64HfKaLbiXK8-f6F4po5tTxBAH')
                            self.hashlist.append(a)
                            self.loadtext.update({'nfthash': self.hashlist})
                            fp.seek(0)
                            json.dump(self.loadtext, fp)
                        else:
                            continue
                    except:
                        continue

    def start(self):
        event.set()
        self.T = threading.Thread(target=self.event)
        self.T.daemon = True
        self.T.start()
        messagebox.showinfo(title='提示', message='追踪中...')

    def addqb(self):
        event.clear()
        # self.w1.insert(1.0, '暂停' + '\n')
        self.addID = tkinter.simpledialog.askstring(title="请输入一个字符或字符串",
                                                    prompt="ID:")
        self.addURL = tkinter.simpledialog.askstring(title="请输入一个字符或字符串",
                                                     prompt="URL:")
        with open('nftbot.json', 'r+', encoding='utf-8') as fp:
            self.loadtext = json.load(fp)
            self.loadtext['urldict'].update({self.addID: self.addURL})
            fp.seek(0)
            json.dump(self.loadtext, fp)
        messagebox.showinfo(title='提示', message='已添加，追踪暂停')

    def conti(self):
        event.set()
        messagebox.showinfo(title='提示', message='继续追踪...')


if __name__ == '__main__':
    a = GUI()
    a.root.mainloop()
