import requests
from DrissionPage import ChromiumPage, ChromiumOptions
from apscheduler.schedulers.blocking import BlockingScheduler
from lxml import etree

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.verify = False
session.headers = {'Content-Type': 'application/json',
                   'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'}
# 创建浏览器配置对象，指定浏览器路径
co = ChromiumOptions().set_browser_path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')


def connect_browser():
    try:
        page = ChromiumPage(addr_or_opts=co)
        return page
    except Exception as e:
        print("连接失败，重试中...")
        return connect_browser()


page = connect_browser()


def job():
    # 用该配置创建页面对象
    # page = ChromiumPage(addr_or_opts=co)
    try:
        page.get('https://equilibria.fi/vote')
        page.wait.ele_loaded('.css-1dveyv5', timeout=30)
        html_data = page.html
    except:
        page = connect_browser()
        page.get('https://equilibria.fi/vote')
        page.wait.ele_loaded('.css-1dveyv5', timeout=30)
        html_data = page.html
    print('等待结束')
    # page.quit()
    alert = []
    alert0 = []
    print("Received HTML content:")
    tree = etree.HTML(html_data)
    # 这里写提取数据的代码

    links = tree.xpath('//div[@class="css-1dveyv5"]')
    for link in links:
        content = link.xpath('.//div[@class="css-zxi8en"]//text()')
        symbol = content[0]
        voter = float(content[1].split('%')[0].replace('K', '000') if '%' in content[1] else '0')
        bribe = float(content[2].split('%')[0].replace('K', '000') if '%' in content[2] else '0')
        if bribe:
            alert.append((symbol, voter, bribe, voter + bribe))
        else:
            alert0.append((symbol, voter, bribe, voter + bribe))
    print(alert)
    return
    alert_sort = sorted(alert, key=lambda x: x[-1], reverse=True)[:3]
    alert0_sort = sorted(alert0, key=lambda x: x[-1], reverse=True)[:3]
    alert_final = []
    for i, j in enumerate(alert_sort):
        alert_final.append(
            f'{i + 1}.{j[0]}\n'
            f'Voter APY:{j[1]}\nBribe:{j[2]}\n总和:{j[3]}')
    json_msg = {
        "msgtype": "text",
        "text": {'content': f'===bribe===\n' + '\n-------\n'.join(alert_final)}
    }
    session.post(
        url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
        json=json_msg)
    alert0_final = []
    for i, j in enumerate(alert0_sort):
        alert0_final.append(
            f'{i + 1}.{j[0]}\n'
            f'Voter APY:{j[1]}\nBribe:{j[2]}\n总和:{j[3]}')
    json_msg = {
        "msgtype": "text",
        "text": {'content': f'===bribe0===\n' + '\n-------\n'.join(alert0_final)}
    }
    session.post(
        url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
        json=json_msg)


job()
scheduler = BlockingScheduler()
scheduler.add_job(job, 'cron', day_of_week='wed', hour=17, minute='25-55/10')
# 启动调度器
scheduler.start()
