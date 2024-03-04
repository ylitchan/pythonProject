import requests as requests
from apscheduler.schedulers.blocking import BlockingScheduler
from bs4 import BeautifulSoup
from collections import Counter
import datetime

session = requests.Session()
session.headers = {
    'Accept-Encoding': 'gzip, deflate',
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
}
alert = set()
scheduler = BlockingScheduler()


@scheduler.scheduled_job('cron', day_of_week='mon-fri', hour='9-15', minute='*/2')
def chaogu():
    try:
        code = set()
        yidong = []
        signal = session.get('http://47.114.88.80/history/{}.html'.format(datetime.datetime.now().strftime('%Y-%m-%d')))
        signal.encoding = "gbk"
        soup = BeautifulSoup(signal.text, 'html.parser')
        ele = soup.find_all('li')
        for i in ele:
            text = i.text.split(' ')
            if text[1] not in code:
                yidong.extend({k for k in text[-1][2:].split('+') if k})
                code.add(text[1])
        cnt = Counter(yidong)
        yidong.clear()
        sort = set(sorted(cnt, key=lambda x: cnt[x], reverse=True)[:11])
        for i in ele:
            text = i.text.split(' ')
            cnt = set(text[-1][2:].split('+')).intersection(sort)
            if text[1] not in alert and cnt:
                alert.add(text[1])
                yidong.append((text[1], ','.join(sorted(cnt))))
        if yidong:
            msg = {
                "token": "e73179f25ade41729eae654a2decec15",
                "title": 'A股异动',
                "content": yidong,
                "topic": "1",
                "template": "html"
            }
            print(session.post(url='http://www.pushplus.plus/send/', json=msg))
        if datetime.datetime.now().hour >= 15:
            alert.clear()
    except:
        pass


scheduler.start()
