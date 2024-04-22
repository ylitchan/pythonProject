import asyncio
import datetime
import threading

from jsonpath_ng.parser import parse
import requests
from DrissionPage import ChromiumPage, ChromiumOptions

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

    def get_price(self):
        try:
            res = session.get(
                f'https://api.coingecko.com/api/v3/simple/price?ids={"%2C".join(price_all.keys())}&vs_currencies=usd',
                headers={'accept': 'application/json'})
            res.raise_for_status()
            price_all.update(res.json())
        except Exception as e:
            pass
        finally:
            return [price_all.get(j, {}).get('usd', 0) for j in self.tokens]

    def get_gas(self):
        try:
            gwei = float(parse('$..high').find(session.get('https://milkroad-api.vercel.app/api/gas').json())[0].value)
            gas[0] = gwei * 0.0007 * price_all.get('ethereum', {}).get('usd', 0)
        except Exception as e:
            pass
        finally:
            return gas[0]

    def push(self, content):
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


def get_profit(biaoqian):
    while True:
        try:
            eth = biaoqian.tab.eles('xpath://*[@class="dashboard_willReceive__vxyQo"]//p')
            price_part = biaoqian.get_price()
            if 'lybra-finance' not in biaoqian.tokens:
                content = [float(j.split('/', 1)[-1].strip().split(' ')[0].strip('%')) for j in
                           [i.text for i in eth]]
                rigid = content[0]
                gas_eth = biaoqian.get_gas()
                profit1 = (1 - price_part[1]) * price_part[0] * rigid - gas_eth
                print({'time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'token': biaoqian.tokens[0],
                       'rigid': rigid, 'gas': gas_eth,
                       'price': price_all, 'profit1': profit1})
                if profit1 >= 50:
                    biaoqian.push(
                        f'token: {biaoqian.tokens[0]}\nrigid: {rigid}\ngas: {gas_eth}\nprice: {price_all}\nprofit1:{profit1}')
                if len(content) == 3:
                    rebase = content[1]
                    discount = content[2] / 100
                    profit2 = (rebase * price_part[0]) * (1 - price_part[1]) + rebase * price_part[
                        0] * discount - gas_eth
                    print(
                        {'time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'token': biaoqian.tokens[0],
                         'rebase': rebase, 'discount': discount, 'gas': gas_eth,
                         'price': price_all, 'profit2': profit2})
                    if profit2 >= 50:
                        biaoqian.push(
                            f'token: {biaoqian.tokens[0]}\nrigid: {rigid}\ngas: {gas_eth}\nprice: {price_all}\nprofit2:{profit2}')
            else:
                lbr = \
                    biaoqian.tab.ele('xpath://*[@class="earn_tabItem__ST764"][1]//div[.//img]').text.strip().split(
                        ' ')[0].strip()
                if lbr:
                    bounty = float(lbr.strip().split(' ')[0].strip())
                    gas_lbr = float(
                        biaoqian.tab.ele('xpath://div[@class="earn_totalCost__yIrMB"]//span').text.split('$')[
                            -1].replace(')', ''))
                    cost = bounty * 0.6
                    profit3 = (bounty - cost) * price_part[0] - gas_lbr
                    print(
                        {'time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'token': biaoqian.tokens[0],
                         'bounty': bounty,
                         'gas': gas_lbr,
                         'cost': cost,
                         'price': price_all, 'profit3': profit3})
                    if profit3 >= 400:
                        biaoqian.push(
                            f"token: {biaoqian.tokens[0]}\nbounty: {bounty}\ngas: {gas_lbr}\ncost: {cost}\nprice: {price_all}\nprofit3: {profit3}")
        except Exception as e:
            print(str(e))
        finally:
            continue


def main():
    # 创建浏览器配置对象，指定浏览器路径
    co = ChromiumOptions().set_browser_path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    # 用该配置创建页面对象
    page = ChromiumPage(addr_or_opts=co)
    stETH = Biaoqian(page.get_tab('558DB823DD391A7998DC3D570B77F295'), ['staked-ether', 'eusd-new', 'ethereum'])
    wstETH = Biaoqian(page.get_tab('38CE41A4521BF1C23A4652072258DF41'), ['wrapped-steth', 'peg-eusd', 'ethereum'])
    wbeth = Biaoqian(page.get_tab('51D1170690049E1D1FDF956E85CAA48D'), ['wrapped-beacon-eth', 'peg-eusd', 'ethereum'])
    rETH = Biaoqian(page.get_tab('DE27B820554C29C22E5405B66EFCFFD2'), ['rocket-pool-eth', 'peg-eusd', 'ethereum'])
    lbr = Biaoqian(page.get_tab('8439534C60028FD6B651D9F58ECB5420'), ['lybra-finance'])  # 创建5个任务
    for biaoqian in [stETH, wstETH, wbeth, rETH, lbr]:
        thread = threading.Thread(target=get_profit, args=(biaoqian,))
        thread.start()


if __name__ == '__main__':
    main()
