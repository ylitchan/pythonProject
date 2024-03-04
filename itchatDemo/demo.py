# -*- encoding=utf8 -*-
__author__ = "颜立全"

import time

import requests
from airtest.core.api import *

auto_setup(__file__)


from poco.drivers.android.uiautomation import AndroidUiautomationPoco
poco = AndroidUiautomationPoco(use_airtest_input=True, screenshot_each_action=False)

def floor(slug):
    nft=requests.get('https://app.nfttrack.ai/api/search?q='+slug).json()['data']['collections'][0]['opensea_slug']
    res=requests.get('https://app.nfttrack.ai/api/collection_info/'+nft)
    return nft+'地板：'+str(res.json()['data']['floor_price'])
def vsend():
    while True:
        msg = poco("com.tencent.mm:id/e7t")[0]
        msgtext=msg.get_text().split('@')[-1]
        print(msgtext)
        if 'baddester' in msgtext:
            msg.click()
            poco("com.tencent.mm:id/iki").click()
            try:
                text(floor(msgtext.replace('baddester ','')))
            except:
                text('没有查询到')
            poco("com.tencent.mm:id/uo").click()


