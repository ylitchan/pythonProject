import datetime
import threading
import time

import requests
from DrissionPage import ChromiumPage, ChromiumOptions
from apscheduler.schedulers.background import BlockingScheduler
from jsonpath_ng.parser import parse
from lxml import etree

scheduler = BlockingScheduler()
session = requests.Session()
session.proxies = {'https': 'http://127.0.0.1:1081', 'http': 'http://127.0.0.1:1081'}
session.headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'}
price_all = {'staked-ether': 0, 'eusd-new': 0, 'ethereum': 0, 'wrapped-steth': 0, 'peg-eusd': 0,
             'wrapped-beacon-eth': 0, 'rocket-pool-eth': 0, 'lybra-finance': 0}
gas = [0.0]


class Biaoqian(object):
    def __init__(self, tab, tokens):
        self.tab = tab
        self.tokens = tokens

    @staticmethod
    def get_price():
        while True:
            try:
                res = session.get(
                    f'https://api.coingecko.com/api/v3/simple/price?ids={"%2C".join(price_all.keys())}&vs_currencies=usd',
                    headers={'accept': 'application/json'})
                res.raise_for_status()
                price_all.update(res.json())
                print(price_all)
            except Exception as e:
                print(str(e))
            finally:
                time.sleep(180)

    @staticmethod
    def get_gas():
        while True:
            try:
                res = session.get('https://milkroad-api.vercel.app/api/gas')
                res.raise_for_status()
                gwei = float(parse('$..high').find(res.json())[0].value)
                gas[0] = gwei * 0.0007 * price_all.get('ethereum', {}).get('usd', 0)
                print(gas)
            except Exception as e:
                print(str(e))
            finally:
                time.sleep(180)

    @staticmethod
    def push(content):
        try:
            headers = {'Content-Type': 'application/json'}
            json = {
                "msgtype": "text",
                "text": {'content': content}
            }
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
                headers=headers, json=json)
        except Exception as e:
            print(str(e))

    def get_profit(self):
        while True:
            try:
                eth = etree.HTML(self.tab.html).xpath('//*[@class="dashboard_willReceive__vxyQo"]//p')
                price_part = [price_all.get(j, {}).get('usd', 0) for j in self.tokens]
                if 'lybra-finance' not in self.tokens:
                    content = [float(j.split('/', 1)[-1].strip().split(' ')[0].strip('%')) for j in
                               [''.join(i.xpath('.//text()')) for i in eth]]
                    rigid = content[0]
                    gas_eth = gas[0]
                    profit1 = (1 - price_part[1]) * price_part[0] * rigid - gas_eth
                    print({'time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'token': self.tokens[0],
                           'rigid': rigid, 'gas': gas_eth,
                           'price': price_all, 'profit1': profit1})
                    if profit1 >= 50:
                        self.push(
                            f'token: {self.tokens[0]}\nrigid: {rigid}\ngas: {gas_eth}\nprice: {price_all}\nprofit1:{profit1}')
                    if len(content) == 3:
                        rebase = content[1]
                        discount = content[2] / 100
                        profit2 = (rebase * price_part[0]) * (1 - price_part[1]) + rebase * price_part[
                            0] * discount - gas_eth
                        print(
                            {'time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'token': self.tokens[0],
                             'rebase': rebase, 'discount': discount, 'gas': gas_eth,
                             'price': price_all, 'profit2': profit2})
                        if profit2 >= 50:
                            self.push(
                                f'token: {self.tokens[0]}\nrigid: {rigid}\ngas: {gas_eth}\nprice: {price_all}\nprofit2:{profit2}')
                else:
                    lbr = \
                        ''.join(etree.HTML(self.tab.html).xpath(
                            '//*[@class="earn_tabItem__ST764"][1]//div[.//img]//text()')).strip().split(
                            ' ')[0].strip()
                    if lbr:
                        bounty = float(lbr.strip().split(' ')[0].strip())
                        gas_lbr = float(
                            ''.join(etree.HTML(self.tab.html).xpath(
                                '//div[@class="earn_totalCost__yIrMB"]//span//text()')).split('$')[
                                -1].replace(')', ''))
                        cost = bounty * 0.6
                        profit3 = (bounty - cost) * price_part[0] - gas_lbr
                        print(
                            {'time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'token': self.tokens[0],
                             'bounty': bounty,
                             'gas': gas_lbr,
                             'cost': cost,
                             'price': price_all, 'profit3': profit3})
                        if profit3 >= 200:
                            self.push(
                                f"token: {self.tokens[0]}\nbounty: {bounty}\ngas: {gas_lbr}\ncost: {cost}\nprice: {price_all}\nprofit3: {profit3}")
            except Exception as e:
                print(str(e))


def main():
    threading.Thread(target=Biaoqian.get_price, args=()).start()
    threading.Thread(target=Biaoqian.get_gas, args=()).start()
    # 创建浏览器配置对象，指定浏览器路径
    co = ChromiumOptions().set_browser_path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe').set_paths(
        local_port=9111, user_data_path=r'D:\DrissionPage')
    # 用该配置创建页面对象
    page = ChromiumPage(addr_or_opts=co)
    # stETH = Biaoqian(page.get_tab(1), ['staked-ether', 'eusd-new', 'ethereum'])
    # wstETH = Biaoqian(page.get_tab(2), ['wrapped-steth', 'peg-eusd', 'ethereum'])
    # wbeth = Biaoqian(page.get_tab(3), ['wrapped-beacon-eth', 'peg-eusd', 'ethereum'])
    # rETH = Biaoqian(page.get_tab(4), ['rocket-pool-eth', 'peg-eusd', 'ethereum'])
    lbr = Biaoqian(page, ['lybra-finance'])
    # 创建5个任务
    for biaoqian in [lbr]:  # [stETH, wstETH, wbeth, rETH, lbr]:
        threading.Thread(target=biaoqian.get_profit, args=()).start()


if __name__ == '__main__':
    main()
