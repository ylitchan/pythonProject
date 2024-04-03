import datetime
import gc
from apscheduler.schedulers.blocking import BlockingScheduler
import requests
from jsonpath_ng import parse

session = requests.Session()
session.headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*',
                   'Hexin-V': 'A2-XDK8JVepbblHWaMIBtVIY_oh8FMOFXWnHKYH8CTLl94F2ieRThm04V2iS',
                   'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'}
# 创建BlockingScheduler对象
scheduler = BlockingScheduler()


def job():
    now = datetime.datetime.now().strftime("%Y%m%d")
    print(datetime.datetime.now(), '任务开始')
    try:
        res = session.post('https://www.iwencai.com/customized/chart/get-robot-data', json={
            "source": "Ths_iwencai_Xuangu",
            "version": "2.0",
            "query_area": "",
            "block_list": "",
            "add_info": "{'urp':{'scene':1,'company':1,'business':1},'contentType':'json','searchInfo':true}",
            "question": "昨日爆量涨停;今日高开;竞价异动说明;涨停原因类别;连续涨停天数;集合竞价评级",
            "perpage": "50",
            "page": 1,
            "secondary_intent": "stock",
            "log_info": "{'input_type':'typewrite'}",
            "rsh": "Ths_iwencai_Xuangu_aw7w649fwmdt9xxywken1478hz1jfcgo"
        }).json()
        data = [
            f"{i + 1}.{g['股票简称']}\n现价:{g[f'最新价']}\n概念:{g[f'涨停原因类别[{now}]']}\n异动:{g[f'竞价异动说明[{now}]']}\n涨幅:{g[f'竞价涨幅[{now}]']}\n连板:{g[f'连续涨停天数[{now}]']}\n评级:{g[f'集合竞价评级[{now}]']}"
            for i, g in enumerate(
                sorted(parse('$..datas').find(res)[0].value, key=lambda x: x[f'竞价涨幅[{now}]'], reverse=True))]
        json = {
            "msgtype": "text",
            "text": {'content': f'===爆B===\n' + '\n-------\n'.join(data)}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=4499f04a-88cf-4100-aef3-7528b2a94d67',
            json=json)
    except Exception as e:
        print(str(e))
    print(datetime.datetime.now(), '任务结束')
    gc.collect()


if __name__ == "__main__":
    job()
    # 设置任务调度
    scheduler.add_job(job, 'cron', hour='09', minute='25', second='03', day_of_week='mon-fri', timezone='Asia/Shanghai')
    # 启动调度器
    scheduler.start()
