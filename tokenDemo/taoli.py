import asyncio
import copy
import time
import aiohttp
from scrapy import Selector
from pyppeteer import launch
import re

import requests

session = requests.Session()
session.proxies = {'https': 'http://127.0.0.1:1080'}


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
    return page


async def get_content(page):
    while True:
        selector = Selector(text=await page.content())
        try:
            eth = selector.xpath('//*[@class="dashboard_willReceive__vxyQo"]//p')
            if eth:
                content = [float(j.split('/', 1)[-1].strip().split(' ')[0].strip('%')) for j in
                           [i.xpath('.//text()').get() for i in eth]]
                rigid = content[0]
                profit1 = 0
                profit2 = 0
                if len(content) == 3:
                    rebase = content[1]
                    discount = content[2]
                    profit2 = 0
                print(rigid, profit1, profit2)
            else:
                lbr = ''.join(selector.xpath('//*[@class="earn_tabItem__ST764"][2]//div[.//img]//text()').getall())
                if lbr:
                    bounty = float(lbr.strip().split(' ')[0].strip())
                    profit3 = 0
                    print(profit3)
        except:
            pass


async def push(title, content):
    json = {
        "token": "e73179f25ade41729eae654a2decec15",
        "title": title,
        "content": content,
        "topic": "1",
        "template": "html"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url='http://www.pushplus.plus/send/', json=json) as res:
            print(res.status)


async def main():
    session.get(url='https://api.coingecko.com/api/v3/simple/price?ids=staked-ether&vs_currencies=usd',headers={'accept':'application/json'} )

    browser = await launch(
        {'headless': False, "dumpio": True, 'executablePath': 'C:\Program Files\Google\Chrome\Application\chrome.exe',
         'autoClose': False, 'logLevel': 'INFO',
         'ignoreDefaultArgs': ['--enable-automation'],
         'args': ['--no-sandbox', '--disable-infobars', '--disable-blink-features=AutomationControlled',
                  r'--user-data-dir=D:\allProjects\pyDemo\tokenDemo\google\Default']
         })

    stETH = await browser.newPage()
    await stETH.evaluateOnNewDocument(
        '() => { Object.defineProperty(navigator, "webdriver", { get: () => undefined }) }'
    )
    # await page.setUserAgent(
    #     'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.00.0.0 Safari/537.36')
    await stETH.setViewport({'width': 1920, 'height': 800})
    await stETH.goto(
        'https://www.coingecko.com/en/coins/celestia')
    await stETH.waitForSelector('.dashboard_bottom_border__wk_4_')
    await stETH.click(
        '#__next > div > div.dashboard_dashboard__v4TLo > div > div > div.dashboard_left__57Tio > div.dashboard_titleList__aPG6z.dashboard_bottom_border__wk_4_ > div:nth-child(5)')
    await stETH.waitForSelector('.dashboard_main__9yhn2')
    await get_content(stETH)
    await browser.close()
    # await page.screenshot({'path': './ccccc.jpg'})
    # await page._client.send('Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': './'})
    # try:
    #     await page.goto('https://www.parliament.uk/contentassets/ad4dd6c9ba9e4f27a7fcdbd4083e1b18/adobestock_128068918.jpeg?width=1000&quality=85')
    # except:
    #     pass
    # script = f'''
    #     var link = document.createElement('a');
    #     link.href = "https://www.parliament.uk/contentassets/ad4dd6c9ba9e4f27a7fcdbd4083e1b18/adobestock_128068918.jpeg?width=1000&quality=85";
    #     link.download = "cccccc";
    #     document.body.appendChild(link);
    #     link.click();
    #     document.body.removeChild(link);
    #     '''
    # await page.evaluate(script)
    # await page.goto('https://committees.parliament.uk/publications/34699/documents/190959/default/')
    # print(await page.content())
    # await page.goto(
    #     'https://www.parliament.uk/business/news/2023/december-2023/lords-debates-the-current-threat-posed-by-north-korea/')
    #
    # # await page.screenshot({'path': 'example.png'})
    # print(await page.content())
    # await browser.close()


asyncio.get_event_loop().run_until_complete(main())
