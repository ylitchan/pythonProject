import datetime
import subprocess
from apscheduler.schedulers.blocking import BlockingScheduler
from scrapy import cmdline

cmdline.execute(['scrapy', 'crawl', 'newAlpha'])
# scheduler = BlockingScheduler()
#
#
# def start_scrapy():
#     print(datetime.datetime.now(), '进程开始')
#     subprocess.run(['scrapy', 'crawl', 'newAlpha'])
#
#
# #
# #
# # subprocess.run(['scrapy', 'crawl', 'newAlpha'])
# scheduler.add_job(start_scrapy, 'cron', day_of_week='mon-sun', hour=21,minute=10)
# # scheduler.add_job(start_scrapy, 'interval', hours=12)  # 每周一到周五的早上8点执行任务
# scheduler.start()
