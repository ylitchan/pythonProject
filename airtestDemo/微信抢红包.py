# -*- encoding=utf8 -*-
__author__ = "颜立全"

from airtest.core.api import *

auto_setup(__file__)


from poco.drivers.android.uiautomation import AndroidUiautomationPoco
poco = AndroidUiautomationPoco(use_airtest_input=True, screenshot_each_action=False)
def get_red_package():
    # 1.获取消息列表元素
    msg_list_elements_pre = poco("com.tencent.mm:id/awv").children()
    msg_list_elements = []keyevent("back")

    for item in msg_list_elements_pre:
        msg_list_elements.insert(0, item)
    for msg_element in msg_list_elements:

        # 2.1 微信红包标识元素
        red_key_element = msg_element.offspring('com.tencent.mm:id/u1')

        # 2.2 是否已经领取元素
        has_click_element = msg_element.offspring('com.tencent.mm:id/tt')

        # 2.3 红包【包含：收到的红包和自己发出去的红包】
        if red_key_element and '挂' not in red_key_element.get_text() and '测' not in red_key_element.get_text():
            print('发现一个红包')
            if has_click_element.exists() and (
                    has_click_element.get_text() == '已领取' or has_click_element.get_text() == '已被领完'):
                print('已经领取过了，略过~')
                continue
            else:
                print('马上抢红包')
                red_key_element.click()
                click_element = poco("com.tencent.mm:id/f4f")
                if click_element.exists():
                    click_element.click()
                keyevent('BACK')

        else:
            print('红包元素不存在')
            continue
        #msg_element.click()

        # click_element = poco("com.tencent.mm:id/cv0")
        # if click_element.exists():
        #     click_element.click()
        #
        #     # 返回
        #     keyevent('BACK')
while True:
     get_red_package()
     print('休眠1秒钟，继续刷新页面，开始抢红包。')
    driver.get("Write your test web address!")
