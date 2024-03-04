import time
import schedule
import subprocess
from scrapy import cmdline


cmdline.execute(['scrapy', 'crawl', 'alpha', '--nolog'])


def work():
    # cmdline.execute(['scrapy', 'crawl', 'alpha', '--nolog'])
    subprocess.Popen('scrapy crawl alpha ')
    print('开始子进程', time.strftime('%Y-%m-%d %H:%M:%S %Z %A'))


schedule.every(910).seconds.do(work)
if __name__ == "__main__":
    work()
    while True:
        schedule.run_pending()
