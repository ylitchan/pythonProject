import datetime
import random
import time
import pyperclip
import pyautogui
time.sleep(5)
print(pyautogui.position())
fp=open('ts2.txt', 'r+', encoding='utf-8').readlines()
print(fp)
lenth = len(fp)
n=0
while True:
    for i in range(0,4):
        # pyautogui.press('up')
        # for alpha.json in range(0, 5):
        #     pyautogui.press('backspace')
        # pyautogui.press('enter')
        # pyautogui.press('enter')

        context='max'
        pyperclip.copy(context)
        pyautogui.hotkey('ctrl','v')
        pyautogui.press('enter')
        pyautogui.hotkey('ctrl', 'tab')
        time.sleep(1)
    print(datetime.datetime.now().strftime('%H:%M:%S'),n)
    n+=1
    # time.sleep(10)
    # n+=1
    # time.sleep(120)MAX BIDDING MAX CHEETAH INSHAALLAH
# while True:
#     if datetime.datetime.now().strftime('%H:%M')=='22:00':
#
#         pyautogui.click(1475,1050)
#         pyautogui.click(1322,1247)
#         break
#     else:
#         print(datetime.datetime.now().strftime('%H:%M'))