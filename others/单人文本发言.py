# 创作人:颜立全
import tkinter as tk
import threading
import tkinter.simpledialog
import selenium.webdriver.edge.service
from selenium import webdriver
from PIL import Image, ImageTk
import datetime
import time
import pyperclip
import pyautogui

event = threading.Event()


class GUI():
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('单人发言gui')
        self.root.geometry("355x300+300+150")
        self.root.resizable(0, 0)
        self.interface()



    def get_img(self, filename, width, height):
        self.im = Image.open(filename).resize((width, height))
        self.im = ImageTk.PhotoImage(self.im)
        return self.im

    def interface(self):
        """"界面编写位置"""
        # self.canvas = tk.Canvas(self.root, width=355, height=300, bd=0, highlightthickness=0)
        # self.im_root = self.get_img('acg.jpeg', 355, 300)
        # self.canvas.create_image(178, 150, image=self.im_root)
        # self.canvas.pack(side='top')
        self.Button0 = tk.Button(self.root, text="start", command=self.start)
        self.Button0.place(x=77, y=270, width=100, height=30)
        self.Button0 = tk.Button(self.root, text="end", command=self.end)
        self.Button0.place(x=178, y=270, width=100, height=30)
        self.w1 = tk.Text(self.root)
        self.w1.place(x=11, y=150, width=333, height=100)
        self.root.bind('<Control-d>', self.draw)

    def draw(self, event):
        a.root.withdraw()

    def sendmsgs(self,jiange):
        fp = open('ts2.txt', 'r+', encoding='utf-8').readlines()
        print(fp)
        lenth = len(fp)
        n = 0
        while n < lenth:
            context = fp.pop()
            pyperclip.copy(context)
            pyautogui.hotkey('ctrl', 'v')
            pyautogui.press('enter')
            # pyautogui.press('up')
            # for alpha.json in range(0, 20):
            #     pyautogui.press('backspace')
            # pyautogui.press('enter')
            # pyautogui.press('enter')
            # pyautogui.hotkey('ctrl', 'tab')
            self.w1.insert(1.0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %f") + context +'\n')
            n += 1
            time.sleep(jiange+1)





    def start(self):
        event.set()
        jiange = tkinter.simpledialog.askfloat(title="间隔",prompt="cd:")

        #币安的频道
        thread = threading.Thread(target=self.sendmsgs, args=[jiange,])
        thread.daemon = True
        thread.start()


    def end(self):
        event.clear()


if __name__ == '__main__':
    a = GUI()
    a.root.mainloop()

