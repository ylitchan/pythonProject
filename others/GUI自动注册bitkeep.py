import datetime
import time
import pyperclip
import pyautogui
for w in ['0xb221ae8361b39158916938303bf498905038b51284d957a9a565db5abe84a0e2max','tube raccoon scare travel goddess enlist screen balcony text payment you board']:
    time.sleep(5)
    print(pyautogui.position())
    # # 新建模拟器
    # pyautogui.click(x=2045, y=590)#新建
    # pyautogui.click(x=1732, y=310)
    # time.sleep(2)
    # # 打开多开模拟器1
    # pyautogui.click(x=1925, y=199)
    # time.sleep(10)
    # # 安装软件，打开软件
    # pyautogui.moveTo(x=2373, y=308)
    # pyautogui.dragTo(x=1231, y=646,duration=2)
    # time.sleep(3)
    # pyautogui.click(x=1182, y=492)#打开软件
    # time.sleep(5)
    # pyautogui.click(x=1001, y=1198)#跳过
    # time.sleep(2)
    # # 选择导入钱包
    # pyautogui.click(x=1284, y=983)
    # time.sleep(2)
    # # 输入第一次密码
    # for i in range(0,6):
    #     pyautogui.click(x=1038, y=978)
    # time.sleep(1.5)
    # pyautogui.click(x=1278, y=862)
    # time.sleep(2)
    # # 输入第二次密码
    # listx=[1274,1519,1519,1281,1038,1038,1282,1518,1280,1038]
    # listy=[976,977,1066,1075,1072,1168,1172,1169,1268,978]
    # for i , alpha.json in zip(listx,listy):
    #     for num in range(0,6):
    #         pyautogui.click(x=i,y=alpha.json)
    #     time.sleep(1.5)
    #     pyautogui.click(x=1278, y=862)
    # # 导入助记词
    # time.sleep(2)
    pyautogui.click(x=1225, y=428)#助记词输入框
    pyperclip.copy(w)
    # time.sleep(2)
    pyperclip.paste()
    pyautogui.click(x=1274, y=674)
    time.sleep(20)
    pyautogui.click(x=1320, y=1266)#立即体验
    # 发现页面
    pyautogui.click(x=1567, y=1301)#发现
    time.sleep(3)
    pyautogui.click(x=1363, y=381)#邀请
    time.sleep(20)
    pyautogui.click(x=1237, y=693)#邀请码框
    # pyperclip.copy('De75eA')
    time.sleep(2)
    pyautogui.typewrite(['D', 'e', '7', '5','e','A'])
    pyautogui.press('enter')
    # pyautogui.hotkey('ctrl','v')
    time.sleep(2)
    pyautogui.click(x=1424, y=841)#确认
    time.sleep(2)
    pyautogui.click(x=1145, y=897)
    time.sleep(2)
    pyautogui.click(x=944, y=136)
    time.sleep(2)
    pyautogui.click(x=1113, y=238)
    time.sleep(2)
    pyautogui.click(x=1177, y=258)#复制id
    time.sleep(2)
    # 复制id发送
    pyautogui.click(x=2423, y=1343)#微信输入
    pyautogui.hotkey('ctrl','v')
    pyautogui.press('enter')
    # 关闭模拟器并删除
    pyautogui.click(x=1928, y=195)#关闭
    pyautogui.click(x=1776, y=395)
    time.sleep(5)
    pyautogui.click(x=2130, y=195)#删除
    pyautogui.click(x=1778, y=400)

    print(datetime.datetime.now().strftime('%H:%M'))