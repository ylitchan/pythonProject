import time

from iFinDPy import *
import os
import sys
import django
import re
import requests
from multiprocessing import Process

sys.path.append('D:\PycharmProjects\demos\djDemo')  # 将项目路径添加到系统搜寻路径当中
os.environ['DJANGO_SETTINGS_MODULE'] = 'djDemo.settings'  # 设置项目的配置文件
django.setup()  # 加载项目配置
# 开始实现功能模块
from myAPP.models import *

thsLogin = THS_iFinDLogin("zsdx325", "916530")


def push(title, content):#微信推送
    json = {
        "token": "e73179f25ade41729eae654a2decec15",
        "title": title,
        "content": content,
        "topic": "0",
        "template": "html"
    }
    with requests.Session() as session:
        with session.post(url='http://www.pushplus.plus/send/', json=json) as res:
            print('推送成功',res.status_code)


def iwencai_demo():
    # 演示如何通过不消耗流量的自然语言语句调用常用数据
    # print('输出资金流向数据')
    # data_wencai_zjlx = THS_WC('主力资金流向', 'stock')
    # if data_wencai_zjlx.errorcode != 0:
    #     print('error:{}'.format(data_wencai_zjlx.errmsg))
    # else:
    #     print(data_wencai_zjlx.data)
    n = 0
    while True:
        try:
            # print(datetime.today().strftime("%Y-%m-%d-%A %H:%M:%S"))
            if not datetime.today().strftime("%A").startswith("S"):#双休不更新
                if int(datetime.today().strftime("%H"))==9 and int(datetime.today().strftime("%M")) in range(25,30):#开盘前5分钟清空原有数据
                    #data_wencai_xny = THS_WC('非st，今日高开，今日竞价量比不小于4，今日获利盘不小于95，昨日跑赢大盘', 'stock')
                    print(datetime.today().strftime("%Y-%m-%d-%A %H:%M:%S") + '清空')
                    Stocks.objects.all().delete()
                    # stocks_create = [Stocks(code=i['thscode'][0], stock=j, latest=i['latest'],changeRatio="%.2f" % i['changeRatio'][0],upperLimit=i['upperLimit']) for i, j in zip([THS_RQ(i, 'changeRatio,latest,upperLimit').data for i in data_wencai_xny.data['股票代码']],data_wencai_xny.data['股票简称'])]
                    # Stocks.objects.bulk_create(stocks_create)
                elif int(datetime.today().strftime("%H")) in range(9, 15):#开盘期间持续更新
                    data_wencai_xny = THS_WC('非st，今日高开，今日竞价量比不小于4，今日获利盘不小于95，昨日跑赢大盘',
                                             'stock')
                    print(datetime.today().strftime("%Y-%m-%d-%A %H:%M:%S") + 'i问财选股')
                    for i, j in zip(data_wencai_xny.data['股票代码'], data_wencai_xny.data['股票简称']):
                        indicators = THS_RQ(i, 'changeRatio,latest,upperLimit').data
                        print("%.2f" % indicators['changeRatio'][0])
                        if Stocks.objects.filter(code=i):#更新已有的
                            Stocks.objects.filter(code=i).update(code=i, stock=j, latest=indicators['latest'],
                                                                 changeRatio="%.2f" % indicators['changeRatio'][0],
                                                                 upperLimit=indicators['upperLimit'])
                        else:#推送及添加新增的
                            push(j, i)
                            Stocks.objects.create(code=i, stock=j, latest=indicators['latest'],
                                                  changeRatio="%.2f" % indicators['changeRatio'][0],
                                                  upperLimit=indicators['upperLimit'])
        except:
            print('错误')



p = Process(target=iwencai_demo)
