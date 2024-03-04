import asyncio
import datetime

from jsonpath_ng.parser import parse
from scrapy import Selector
from pyppeteer import launch
import requests

session = requests.Session()
session.proxies = {'https': 'http://127.0.0.1:1080', 'http': 'http://127.0.0.1:1080'}
session.headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'}
price_all = {}
gas = [0.0]


class Biaoqian(object):
    def __init__(self, page, tokens):
        self.page = page
        self.tokens = tokens

    def get_price(self):
        try:
            price = session.get(
                f'https://api.coingecko.com/api/v3/simple/price?ids={"%2C".join(self.tokens)}&vs_currencies=usd',
                headers={'accept': 'application/json'}).json()
            price_all.update(
                {j: price.get(j).get('usd') for j in self.tokens})
        except Exception as e:
            pass
        finally:
            return {j: price_all.get(j, 0.0) for j in self.tokens}

    def get_gas(self):
        try:
            gwei = float(parse('$..high').find(session.get('https://milkroad-api.vercel.app/api/gas').json())[0].value)
            gas[0] = gwei * 0.0007 * price_all.get('ethereum', 0.0)
        except Exception as e:
            pass
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


async def create_page(browser, num):
    page = await browser.newPage()
    await page.evaluateOnNewDocument(
        '() => { Object.defineProperty(navigator, "webdriver", { get: () => undefined }) }'
    )
    # await page.setUserAgent(
    #     'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36')
    await page.setViewport({'width': 1920, 'height': 800})
    await page.goto(
        'https://lybra.finance/dashboard')
    await page.waitForSelector('.dashboard_topCoinList__Jfzsu')
    await page.click(
        f'#__next > div > div.dashboard_dashboard__v4TLo > div > div > div.dashboard_right___hw_5 > div > div.dashboard_dashMain__RLWHd > div.dashboard_topCoinList__Jfzsu > div:nth-child({num})')
    await page.waitForSelector('.dashboard_main__9yhn2')
    return page


async def get_profit(biaoqians):
    while True:
        for biaoqian in biaoqians:
            try:
                selector = Selector(text=await biaoqian.page.content())
                eth = selector.xpath('//*[@class="dashboard_willReceive__vxyQo"]//p')
                price_part = biaoqian.get_price()
                price = [price_part.get(j, 0) for j in biaoqian.tokens]
                if eth:
                    content = [float(j.split('/', 1)[-1].strip().split(' ')[0].strip('%')) for j in
                               [i.xpath('.//text()').get() for i in eth]]
                    rigid = content[0]
                    gas_eth = biaoqian.get_gas()
                    profit1 = (1 - price[1]) * price[0] * rigid - gas_eth
                    print({'time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'token': biaoqian.tokens[0],
                           'rigid': rigid, 'gas': gas_eth,
                           'price': price_part, 'profit1': profit1})
                    if profit1 >= 50:
                        biaoqian.push(
                            f'token: {biaoqian.tokens[0]}\nrigid: {rigid}\ngas: {gas_eth}\nprice: {price_part}\nprofit1:{profit1}')
                    if len(content) == 3:
                        rebase = content[1]
                        discount = content[2] / 100
                        profit2 = (rebase * price[0]) * (1 - price[1]) + rebase * price[
                            0] * discount - gas_eth
                        print(
                            {'time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'token': biaoqian.tokens[0],
                             'rebase': rebase, 'discount': discount, 'gas': gas_eth,
                             'price': price_part, 'profit2': profit2})
                        if profit2 >= 50:
                            biaoqian.push(
                                f'token: {biaoqian.tokens[0]}\nrigid: {rigid}\ngas: {gas_eth}\nprice: {price_part}\nprofit2:{profit2}')
                else:
                    lbr = ''.join(
                        selector.xpath(
                            '//*[@class="earn_tabItem__ST764"][1]//div[.//img]//text()').getall()).strip().split(
                        ' ')[0].strip()
                    if lbr:
                        bounty = float(lbr.strip().split(' ')[0].strip())
                        gas_lbr = float(
                            selector.xpath('//div[@class="earn_totalCost__yIrMB"]//span//text()').get().split('$')[
                                -1].replace(')', ''))
                        cost = bounty * 0.6
                        profit3 = (bounty - cost) * price[0] - gas_lbr
                        print(
                            {'time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'token': biaoqian.tokens[0],
                             'bounty': bounty,
                             'gas': gas_lbr,
                             'cost': cost,
                             'price': price_part, 'profit3': profit3})
                        if profit3 >= 100:
                            biaoqian.push(
                                f"token: {biaoqian.tokens[0]}\nbounty: {bounty}\ngas: {gas_lbr}\ncost: {cost}\nprice: {price_part}\nprofit3: {profit3}")
            except Exception as e:
                print(str(e))
            finally:
                await asyncio.sleep(3)


async def main():
    browser = await launch(
        {'headless': False, "dumpio": True, 'executablePath': 'C:\Program Files\Google\Chrome\Application\chrome.exe',
         'autoClose': False, 'logLevel': 'INFO',
         'ignoreDefaultArgs': ['--enable-automation'],
         'args': ['--no-sandbox', '--disable-infobars', '--disable-blink-features=AutomationControlled',
                  r'--user-data-dir=C:\Users\颜立全\AppData\Local\Google\Chrome\User Data\Default']
         })

    stETH = await browser.newPage()
    await stETH.evaluateOnNewDocument(
        '() => { Object.defineProperty(navigator, "webdriver", { get: () => undefined }) }'
    )
    # await page.setUserAgent(
    #     'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.00.0.0 Safari/537.36')
    await stETH.setViewport({'width': 1920, 'height': 800})
    await stETH.goto(
        'https://lybra.finance/dashboard')
    await stETH.waitForSelector('.dashboard_bottom_border__wk_4_')
    await stETH.click(
        '#__next > div > div.dashboard_dashboard__v4TLo > div > div > div.dashboard_left__57Tio > div.dashboard_titleList__aPG6z.dashboard_bottom_border__wk_4_ > div:nth-child(5)')
    await stETH.waitForSelector('.dashboard_main__9yhn2')
    stETH = Biaoqian(stETH, ['staked-ether', 'eusd-new', 'ethereum'])
    wstETH = await create_page(browser, 3)
    wstETH = Biaoqian(wstETH, ['wrapped-steth', 'peg-eusd', 'ethereum'])
    wbeth = await create_page(browser, 4)
    wbeth = Biaoqian(wbeth, ['wrapped-beacon-eth', 'peg-eusd', 'ethereum'])
    rETH = await create_page(browser, 5)
    rETH = Biaoqian(rETH, ['rocket-pool-eth', 'peg-eusd', 'ethereum'])
    lbr = await browser.newPage()
    await lbr.goto(
        'https://lybra.finance/dashboard')
    await lbr.waitForSelector('.dashboard_bottom_border__wk_4_')
    await lbr.click(
        '#__next > div > div.dashboard_dashboard__v4TLo > div > div > div.dashboard_left__57Tio > div:nth-child(5) > div:nth-child(4)')
    await lbr.waitForSelector('#Bounty')
    lbr = Biaoqian(lbr, ['lybra-finance'])
    biaoqians = [stETH, wstETH, wbeth, rETH, lbr]
    await get_profit(biaoqians)
    await browser.close()


asyncio.get_event_loop().run_until_complete(main())
