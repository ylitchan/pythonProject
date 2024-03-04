# 创作人:颜立全
import random
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

event = threading.Event()


class GUI():
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('dc频道发言')
        self.root.geometry("355x300+300+150")
        self.root.resizable(0, 0)
        self.interface()
        self.options = webdriver.EdgeOptions()
        # self.options.headless = True
        # self.options.add_argument(r'--user-data-dir=D:\PycharmProjects\demos\User Data')
        self.service = webdriver.edge.service.Service(executable_path="msedgedriver.exe")
        self.driver = webdriver.Edge(options=self.options)

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

    def login(self, channel, id, pw):
        self.driver.get('https://discord.com/login?redirect_to=%2Fchannels%2F' + channel.replace('/', '%2F'))

        name = self.driver.find_element(By.XPATH,
                                        '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[1]/div/div[2]/input')
        password = self.driver.find_element(By.XPATH,
                                            '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/div[2]/div/input')
        name.send_keys(id)
        password.send_keys(pw)
        self.driver.find_element(By.XPATH,
                                 '//*[@id="app-mount"]/div[2]/div/div[1]/div/div/div/div/form/div/div/div[1]/div[2]/button[2]').click()

    def sendmsg(self, id, pw, channel, st, bt):
        """按钮事件，一直循环"""
        self.login(channel, id, pw)
        WebDriverWait(self.driver, 10, 0.5).until(
            EC.visibility_of_element_located((By.CLASS_NAME, 'messageContent-2t3eCI')),
            message='超时啦!')
        while True:
            event.wait()
            oldtime = time.time()
            ActionChains(self.driver).key_down(Keys.NUMPAD1).key_up(Keys.NUMPAD1).send_keys(Keys.ENTER).perform()
            a = ['']
            while True:
                try:
                    a[-1] = self.driver.find_elements(By.CLASS_NAME, 'messageContent-2t3eCI')[-1].get_attribute('id')
                    break
                except:
                    continue
            n = 0
            while True:
                newtime = time.time()
                try:
                    b = self.driver.find_elements(By.CLASS_NAME, 'messageContent-2t3eCI')[-1].get_attribute('id')

                except:
                    continue
                if a[-1] != b and n == 0:
                    ActionChains(self.driver).key_down(Keys.UP).key_up(Keys.UP).send_keys(Keys.BACKSPACE).send_keys(
                        Keys.ENTER).send_keys(Keys.ENTER).perform()
                    n += 1
                elif n == 2 or newtime - oldtime > 5:
                    break
                elif n == 1:

                    while True:
                        try:
                            c = self.driver.find_elements(By.CLASS_NAME, 'messageContent-2t3eCI')[-1].get_attribute(
                                'id')

                        except:
                            continue
                        if c == b and n==1:
                            ActionChains(self.driver).key_down(Keys.NUMPAD0).key_up(Keys.NUMPAD0).send_keys(
                                Keys.BACKSPACE).perform()

                            ActionChains(self.driver).key_down(Keys.UP).key_up(Keys.UP).send_keys(
                                Keys.BACKSPACE).send_keys(Keys.ENTER).send_keys(Keys.ENTER).perform()
                            n += 1
                        elif n == 2 or newtime - oldtime > 5:
                            break
                    self.w1.insert(1.0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %f") + '\n')
            time.sleep(5)
    def start(self):
        event.set()
        id = tkinter.simpledialog.askstring(title="dc", prompt="id:")
        pw = tkinter.simpledialog.askstring(title="dc", prompt="pw:")
        channel = tkinter.simpledialog.askstring(title="dc", prompt="channel:")
        st = tkinter.simpledialog.askfloat(title="dc", prompt="间隔/秒:")
        bt = tkinter.simpledialog.askstring(title="dc", prompt="是否开启随机频道(1是):")
        thread = threading.Thread(target=self.sendmsg, args=[id, pw, channel, st, bt])
        thread.daemon = True
        thread.start()
        messagebox.showinfo(title='提示', message='开启')

    def end(self):
        event.clear()
        webdriver.Edge().quit()
        messagebox.showinfo(title='提示', message='结束')


if __name__ == '__main__':
    a = GUI()
    a.root.mainloop()
