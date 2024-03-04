import threading
import selenium.webdriver.edge.service
# from discord_webhook import DiscordWebhook
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from flask import Flask, redirect, url_for, request, render_template
from decimal import Decimal


class App(Flask):
    def __init__(self, name):
        super().__init__(name)
        # 设置浏览器参数
        self.options = webdriver.EdgeOptions()
        self.options.headless = True
        self.service = webdriver.edge.service.Service()#executable_path="D:/msedgedriver.exe"
        self.options.add_argument(
            "user-agent=Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/103.0.5060.134 Mobile Safari/537.36 Edg/103.0.1264.71")
        # 设置容器
        self.tokenhreflist = []
        self.tokenvaluelist = []
        self.tokentokenlist = []
        self.tokenfeelist = []
        self.interhreflist = []
        self.intervaluelist = []
        self.intertokenlist = []
        self.interfeelist = []
        self.txshreflist = []
        self.txsvaluelist = []
        self.txstokenlist = []
        self.txsfeelist = []
        self.methodlist = []
        self.tokencrlist = []

    def listinit(self):
        # 初始化容器
        self.tokenhreflist = []
        self.tokenvaluelist = []
        self.tokentokenlist = []
        self.tokenfeelist = []
        self.interhreflist = []
        self.intervaluelist = []
        self.intertokenlist = []
        self.interfeelist = []
        self.txshreflist = []
        self.txsvaluelist = []
        self.txstokenlist = []
        self.txsfeelist = []
        self.methodlist = []
        self.tokencrlist = []

    def tokendata(self, wallet):
        # 初始化浏览器，打开20交易，获取页数数据
        tokendriver = webdriver.Edge(options=self.options, service=self.service)

        def token20(url,num):
            tokendriver.get('https://' + url + '/tokentxns?a=' + wallet + '&ps=100&p=' + num)
            for i in range(1, 101):
                try:
                    href = tokendriver.find_element(By.XPATH,
                                                    '//*[@id="tblResult"]/tbody/tr[' + str(i) + ']/td[2]/span/a')
                    self.tokenhreflist.append(href.get_attribute('href'))
                    token = tokendriver.find_element(By.XPATH,
                                                     '//*[@id="tblResult"]/tbody/tr[' + str(i) + ']/td[9]').text
                    print(token.split()[-1])
                    self.tokentokenlist.append(token.split()[-1])
                    cr = tokendriver.find_element(By.XPATH,
                                                  '//*[@id="tblResult"]/tbody/tr[' + str(i) + ']/td[6]').text
                    self.tokencrlist.append(cr)
                    value = tokendriver.find_element(By.XPATH,
                                                     '//*[@id="tblResult"]/tbody/tr[' + str(i) + ']/td[8]').text
                    if cr != 'OUT':
                        value = float(value.replace(',',''))
                    else:
                        value = -float(value.replace(',',''))
                    value = float(value)
                    self.tokenvaluelist.append(value)
                    self.tokenfeelist.append(0)
                except:
                    break
        # 数据爬取函数
        for url in ['etherscan.io', 'bscscan.com']:
            try:
                tokendriver.get('https://' + url + '/tokentxns?a=' + wallet + '&ps=100&p=1')
                page = tokendriver.find_element(By.XPATH,
                                                '//*[@id="ContentPlaceHolder1_divTopPagination"]/nav/ul/li[3]/span/strong[2]').text
            except:
                page = '1'
                pass
            for number in range(1, int(page) + 1):
                token20(url,str(number))
        tokendriver.close()
        # def token20(token,num):
        #     for i in ['etherscan.io','bscscan.com']:
        #     tokendriver.get('https://'+token+'/tokentxns?a=' + wallet + '&ps=100&p=' + num)
        #     for i in range(1, 101):
        #         try:
        #             href = tokendriver.find_element(By.XPATH,
        #                                          '//*[@id="tblResult"]/tbody/tr[' + str(i) + ']/td[2]/span/a')
        #             self.tokenhreflist.append(href.get_attribute('href'))
        #             token = tokendriver.find_element(By.XPATH,
        #                                          '//*[@id="tblResult"]/tbody/tr[' + str(i) + ']/td[9]').text
        #
        #             self.tokentokenlist.append(token.split()[-1])
        #             cr = tokendriver.find_element(By.XPATH,
        #                                          '//*[@id="tblResult"]/tbody/tr[' + str(i) + ']/td[6]').text
        #             self.tokencrlist.append(cr)
        #             value = tokendriver.find_element(By.XPATH, '//*[@id="tblResult"]/tbody/tr[' + str(i) + ']/td[8]').text
        #             if cr != 'OUT':
        #                 value = float(value)
        #             else:
        #                 value = -float(value)
        #             value = float(value)
        #             self.tokenvaluelist.append(value)
        #             self.tokenfeelist.append(0)
        #         except:
        #             break
        #
        # # 获取erc20数据
        #


    def interdata(self, wallet):
        # 打开Internal交易，获取数据，存放在列表中
        interdriver = webdriver.Edge(options=self.options, service=self.service)
        interdriver.get('https://etherscan.io/txsInternal?a=' + wallet + '&ps=100&p=1')
        page = interdriver.find_element(By.XPATH,
                                        '//*[@id="ContentPlaceHolder1_divTopPagination"]/nav/ul/li[3]/span/strong[2]').text

        def intertxs(num):
            interdriver.get('https://etherscan.io/txsInternal?a=' + wallet + '&ps=100&p='+num)
            for i in range(1, 101):
                try:
                    href = interdriver.find_element(By.XPATH,
                                                    '//*[@id="ctl00"]/div[3]/div[2]/table/tbody/tr[' + str(
                                                        i) + ']/td[4]/span/a')
                    self.interhreflist.append(href.get_attribute('href'))
                    value = interdriver.find_element(By.XPATH,
                                                     '//*[@id="ctl00"]/div[3]/div[2]/table/tbody/tr[' + str(
                                                         i) + ']/td[9]').text
                    self.intertokenlist.append('(Ether)')
                    value = float(value.replace(' Ether', '').replace(',',''))
                    self.intervaluelist.append(value)
                    self.interfeelist.append(0)
                except:
                    break

        # 获取内部交易数据
        for number in range(1, int(page) + 1):
            intertxs(str(number))
        interdriver.close()

    def txsdata(self, wallet):
        # 打开txs交易，获取数据，存放在列表中
        txsdriver = webdriver.Edge(options=self.options, service=self.service)

        try:
            txsdriver.get('https://etherscan.io/txs?a=' + wallet + '&ps=100&p=1')
            page = txsdriver.find_element(By.XPATH,
                                          '//*[@id="ContentPlaceHolder1_topPageDiv"]/nav/ul/li[3]/span/strong[2]').text
        except:
            page = '1'
            pass

        def txns(num):
            txsdriver.get('https://etherscan.io/txs?a=' + wallet + '&ps=100&p=' + num)
            for i in range(1, 101):
                try:
                    try:
                        href = txsdriver.find_element(By.XPATH,
                                                      '//*[@id="paywall_mask"]/table/tbody/tr[' + str(
                                                          i) + ']/td[2]/span/a')
                    except:
                        href = txsdriver.find_element(By.XPATH,
                                                      '//*[@id="paywall_mask"]/table/tbody/tr[' + str(
                                                          i) + ']/td[2]/span[2]/a')
                        pass

                    self.txshreflist.append(href.get_attribute('href'))
                    method = txsdriver.find_element(By.XPATH,
                                                    '//*[@id="paywall_mask"]/table/tbody/tr[' + str(i) + ']/td[3]').text

                    self.methodlist.append(method)
                    cr = txsdriver.find_element(By.XPATH,
                                                '//*[@id="paywall_mask"]/table/tbody/tr[' + str(i) + ']/td[8]').text
                    value = txsdriver.find_element(By.XPATH,
                                                   '//*[@id="paywall_mask"]/table/tbody/tr[' + str(i) + ']/td[10]').text
                    self.txstokenlist.append('(Ether)')
                    fee = txsdriver.find_element(By.XPATH,
                                                 '//*[@id="paywall_mask"]/table/tbody/tr[' + str(i) + ']/td[11]').text
                    if cr != 'OUT':
                        value = float(value.replace(' Ether', '').replace(',',''))
                        self.txsfeelist.append(0)
                    else:
                        value = -float(value.replace(' Ether', '').replace(',',''))
                        self.txsfeelist.append(float(fee))
                    self.txsvaluelist.append(value)

                except:
                    break

        # 获取以太坊账户交易记录
        for number in range(1, int(page) + 1):
            txns(str(number))
        txsdriver.close()


app = App(__name__)


@app.route('/', methods=['POST', 'GET'])
def unikit():
    return render_template('wallet.html')


@app.route('/login', methods=['POST', 'GET'])
def watchwallet():
    wallet = request.form['search']
    # 创建线程
    tokenthread = threading.Thread(target=app.tokendata, name='tokenthread', args=(wallet,))
    tokenthread.start()
    interthread = threading.Thread(target=app.interdata, name='interthread', args=(wallet,))
    interthread.start()
    txsthread = threading.Thread(target=app.txsdata, name='txsthread', args=(wallet,))
    txsthread.start()
    # 设置线程保护
    txsthread.join()
    interthread.join()
    tokenthread.join()
    # 整理合并数据，得到项目和对应的进出价格
    driver = webdriver.Edge(options=app.options, service=app.service)
    tokenlist = app.tokentokenlist + app.intertokenlist + app.txstokenlist
    hreflist = app.tokenhreflist + app.interhreflist + app.txshreflist
    feelist = app.tokenfeelist + app.interfeelist + app.txsfeelist
    valuelist = app.tokenvaluelist + app.intervaluelist + app.txsvaluelist
    tokendict = {}
    ethvalue = 0
    n = 0
    for i in hreflist:
        driver.get(i)
        try:
            nft = driver.find_element(By.CLASS_NAME, 'text-truncate').text
            if nft == '':
                nft = app.methodlist[n + len(app.methodlist) - len(tokenlist)]
                action = '无token交易'
            else:
                action = driver.find_element(By.XPATH, '//*[@id="ContentPlaceHolder1_maintable"]/div[5]').text

        except:
            nft = app.methodlist[n + len(app.methodlist) - len(tokenlist)]
            action = '无token交易'
            pass
        nft = nft + tokenlist[n]
        if n < len(app.tokentokenlist):
            if app.tokencrlist[n] != ' IN':
                fee = driver.find_element(By.ID, 'ContentPlaceHolder1_spanTxFee').text.split()[0]
                feelist[n] = float(fee)
        else:
            ethvalue = ethvalue + valuelist[n] - feelist[n]
        if nft not in tokendict:
            tokendict[nft] = {'entry': 0, 'exit': 0, 'fee': 0, 'token': tokenlist[n], 'action': {'IN':{},'OUT':{}}}
        if valuelist[n] > 0:
            tokendict[nft]['exit'] = tokendict[nft]['exit'] + valuelist[n]
            tokendict[nft]['action']['IN'][action] = i
        else:
            tokendict[nft]['entry'] = tokendict[nft]['entry'] - valuelist[n]
            tokendict[nft]['action']['OUT'][action] = i
        tokendict[nft]['fee'] = tokendict[nft]['fee'] + feelist[n]
        print(n)
        n += 1
    app.listinit()
    return render_template('wallet.html', eth=ethvalue, result=tokendict)


if __name__ == '__main__':
    app.run(host='127.0.0.2',port=8080, debug=True)
