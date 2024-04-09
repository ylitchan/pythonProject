import datetime
import gc
from apscheduler.schedulers.blocking import BlockingScheduler
import requests
from jsonpath_ng import parse

session = requests.Session()
session.headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*',
                   'Cookie':'other_uid=Ths_iwencai_Xuangu_0oslwjb9tn4eld7nk5n3rre3djy9xbi3; ta_random_userid=8z37r73slj; cid=9bda78828a8699f783b5b259fa9c111e1708655704; cid=9bda78828a8699f783b5b259fa9c111e1708655704; ComputerID=9bda78828a8699f783b5b259fa9c111e1708655704; WafStatus=0; u_ukey=A10702B8689642C6BE607730E11E6E4A; u_uver=1.0.0; u_dpass=xTh8aNFtKIS6TJbUWRvdj98bTT6CMAzB%2FjJGRa9pnS9DF%2BwaksN1dsSGwpD7dPB7%2FsBAGfA5tlbuzYBqqcUNFA%3D%3D; u_did=AC0F414F4C1F478BACE0F17D8A91AB44; u_ttype=WEB; THSSESSID=9b435792f59de5c8079ae01ebf; user=MDpMaXRjaGFubzo6Tm9uZTo1MDA6NzI0MTU2NTA4OjcsMTExMTExMTExMTEsNDA7NDQsMTEsNDA7NiwxLDQwOzUsMSw0MDsxLDEwMSw0MDsyLDEsNDA7MywxLDQwOzUsMSw0MDs4LDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAxLDQwOzEwMiwxLDQwOjo6OjcxNDE1NjUwODoxNzEyNjU0ODk5Ojo6MTcxMjAzNjk0MDo4NjQwMDowOjFkMjI0ZmMxNDM5ZmFiYjE5YjI4NjBhYzAyNjMzNjNlMDpkZWZhdWx0XzQ6MQ%3D%3D; userid=714156508; u_name=Litchano; escapename=Litchano; ticket=98382e9f4a4649d60deaadde9e6986dc; user_status=0; utk=0a4afb3b1e96b12141c1eefaf1590bfa; v=A78hB4vg5eMZ9uH_S6ixpSKITphMpBN3LfgXOFGNW261YNFGWXSjlj3Ip5Ni',
                   # 'Hexin-V': 'A78hB4vg5eMZ9uH_S6ixpSKITphMpBN3LfgXOFGNW261YNFGWXSjlj3Ip5Ni',
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
            f"{i + 1}.{g.get('股票简称', '-')}\n现价:{g.get(f'最新价', '-')}\n概念:{g.get(f'涨停原因类别[{now}]', '-')}\n异动:{g.get(f'竞价异动说明[{now}]', '-')}\n涨幅:{g.get(f'竞价涨幅[{now}]', '-')}\n连板:{g.get(f'连续涨停天数[{now}]', '-')}\n评级:{g.get(f'集合竞价评级[{now}]', '-')}"
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
    scheduler.add_job(job, 'cron', hour='*', minute='*/10', second='*', day_of_week='mon-fri', timezone='Asia/Shanghai')
    # 启动调度器
    scheduler.start()
