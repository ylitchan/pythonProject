import re
import threading
import selenium.webdriver.edge.service
# from discord_webhook import DiscordWebhook
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from flask import Flask, redirect, url_for, request, render_template
from decimal import Decimal

tokenLock = threading.Lock()
interLock = threading.Lock()
txsLock = threading.Lock()


class App(Flask):
    def __init__(self, name):
        super().__init__(name)
        # 设置浏览器参数
        self.options = webdriver.EdgeOptions()
        self.options.headless = True
        self.service = webdriver.edge.service.Service()  # executable_path="D:/msedgedriver.exe"
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

        self.tokencrlist = []


app = App(__name__)


@app.route('/', methods=['POST', 'GET'])
def unikit():
    return render_template('wallet.html')


@app.route('/login', methods=['POST', 'GET'])
def watchwallet():
    wallet = request.form['search']
    threadlist = []

    class TokenThread(threading.Thread):
        def __init__(self, url, datanum):
            threading.Thread.__init__(self)
            self.url = url
            self.datanum = datanum

        def run(self):
            tokendata(self.url, self.datanum)

    class InterThread(threading.Thread):
        def __init__(self, url, datanum):
            threading.Thread.__init__(self)
            self.url = url
            self.datanum = datanum

        def run(self):
            interdata(self.url, self.datanum)

    class TxsThread(threading.Thread):
        def __init__(self, url, datanum):
            threading.Thread.__init__(self)
            self.url = url
            self.datanum = datanum

        def run(self):
            txsdata(self.url, self.datanum)

    with open('watchwallet.json', 'r+') as fp:
        loadtext = json.load(fp)
        if wallet not in loadtext:
            loadtext[wallet] = {"bscscan.com": {"token20num": 0, "intertxsnum": 0, "txsnum": 0, "project": {}},
                                "etherscan.io": {"token20num": 0, "intertxsnum": 0, "txsnum": 0, "project": {}}}

        def func(html):
            projectset = set()
            action = re.findall(r'Transaction Action:.*?Tokens Transferred:', html, re.S)
            print('这是action', action)
            if action:
                of = re.findall(r'of.*?\n', action[0], re.S)
                print(of)
                i = 0
                while i < len(of):
                    print('这是i', i)
                    if wallet.lower() in of[i]:
                        project = re.search(r'of(.*?)\)', of[i], re.S).group()
                        for j in range(i + 1, len(of)):
                            if '0x' in of[j]:

                                break
                            else:
                                try:
                                    projectset.add(re.search('\[\d+?]', of[j]).group() + project)
                                except:
                                    projectset.add('[]' + project)
                                    pass
                            print('这是j', j)
                            i = j
                    else:
                        i += 1
            return projectset
        def tokendata(url, datanum):
            # 初始化浏览器，打开20交易，获取页数数据
            tokendriver = webdriver.Edge(options=app.options, service=app.service)
            addnum = 0
            # 数据爬取函数
            # def token20(num, total):
            tokendriver.get('https://' + url + '/address/' + wallet)
            loadtext[wallet][url]['totaltokenvalue'] = tokendriver.find_element(By.XPATH,
                                                '//*[@id="ContentPlaceHolder1_divSummary"]/div[1]/div[1]/div/div[2]/div[1]/div[2]').text
            loadtext[wallet][url]['totalvalue'] = tokendriver.find_element(By.XPATH,
                                                                                '//*[@id="ContentPlaceHolder1_divSummary"]/div[1]/div[1]/div/div[2]/div[2]/div[2]').text

            print(loadtext[wallet][url]['totalvalue'],loadtext[wallet][url]['totaltokenvalue'])
            tokendriver.get('https://' + url + '/tokentxns?a=' + wallet + '&ps=100&p=1')
            try:

                page = tokendriver.find_element(By.XPATH,
                                                '//*[@id="ContentPlaceHolder1_divTopPagination"]/nav/ul/li[3]/span/strong[2]').text

            except:
                page = 1
                pass
            try:
                total = tokendriver.find_element(By.XPATH, '//*[@id="ContentPlaceHolder1_divTopPagination"]/p').text
                total = int(total.split()[3])
            except:
                total = 0
                pass
            loadtext[wallet][url]['token20num'] = total
            print(total, page)
            tokenLock.acquire()
            for number in range(1, int(page) + 1):
                if addnum < total - datanum:
                    tokendriver.get('https://' + url + '/tokentxns?a=' + wallet + '&ps=100&p=' + str(number))
                    for pagenum in range(1, 101):
                        if addnum < total - datanum:
                            try:
                                href = tokendriver.find_element(By.XPATH,
                                                                '//*[@id="tblResult"]/tbody/tr[' + str(
                                                                    pagenum) + ']/td[2]/span/a')
                                token = tokendriver.find_element(By.XPATH,
                                                                 '//*[@id="tblResult"]/tbody/tr[' + str(
                                                                     pagenum) + ']/td[9]').text
                                cr = tokendriver.find_element(By.XPATH,
                                                              '//*[@id="tblResult"]/tbody/tr[' + str(
                                                                  pagenum) + ']/td[6]').text
                                value = tokendriver.find_element(By.XPATH,
                                                                 '//*[@id="tblResult"]/tbody/tr[' + str(
                                                                     pagenum) + ']/td[8]').text
                            except:
                                href = tokendriver.find_element(By.XPATH,
                                                                '//*[@id="tblResult"]/tbody/tr/td[2]/span/a')
                                token = tokendriver.find_element(By.XPATH,
                                                                 '//*[@id="tblResult"]/tbody/tr/td[9]').text
                                cr = tokendriver.find_element(By.XPATH,
                                                              '//*[@id="tblResult"]/tbody/tr]/td[6]').text
                                value = tokendriver.find_element(By.XPATH,
                                                                 '//*[@id="tblResult"]/tbody/tr/td[8]').text
                                pass
                            app.tokenhreflist.append(href.get_attribute('href'))

                            app.tokentokenlist.append(token.split()[-1])

                            app.tokencrlist.append(cr)

                            if cr != 'OUT':
                                value = float(value.replace(',', ''))
                            else:
                                value = -float(value.replace(',', ''))
                            app.tokenvaluelist.append(value)
                            app.tokenfeelist.append(0)
                            addnum += 1
                        else:
                            break
                else:
                    break

            # 数据爬取
            n = 0
            for href in app.tokenhreflist:
                tokendriver.get(href)
                html=tokendriver.find_element(By.XPATH,'/html').text
                if app.tokencrlist[n] != ' IN':
                    fee = tokendriver.find_element(By.ID, 'ContentPlaceHolder1_spanTxFee').text.split()[0]
                    app.tokenfeelist[n] = float(fee)
                projectset=func(html)
                if projectset:
                # timestamp = tokendriver.find_element(By.ID, 'ContentPlaceHolder1_divTimeStamp').text.split('ago')[-1]
                # action = action + timestamp
                    for xm in projectset:
                        project = xm + app.tokentokenlist[n]
                        if project not in loadtext[wallet][url]['project']:
                            loadtext[wallet][url]['project'][project] = {'entry': 0, 'exit': 0, 'fee': 0,
                                                                         'token': app.tokentokenlist[n],
                                                                         'action': {'IN': {}, 'OUT': {}}}
                        if app.tokenvaluelist[n] > 0:
                            loadtext[wallet][url]['project'][project]['exit'] = loadtext[wallet][url]['project'][project][
                                                                                    'exit'] + app.tokenvaluelist[n]/len(projectset)
                            # loadtext[wallet][url]['project'][project]['action']['IN'][action] = href
                        else:
                            loadtext[wallet][url]['project'][project]['entry'] = loadtext[wallet][url]['project'][project][
                                                                                     'entry'] - app.tokenvaluelist[n]/len(projectset)
                            # loadtext[wallet][url]['project'][project]['action']['OUT'][action] = href
                        loadtext[wallet][url]['project'][project]['fee'] = loadtext[wallet][url]['project'][project]['fee'] + \
                                                                           app.tokenfeelist[n]/len(projectset)
                        print(loadtext[wallet][url]['project'])
                n += 1
            app.tokenhreflist = []
            app.tokenvaluelist = []
            app.tokentokenlist = []
            app.tokenfeelist = []
            app.tokencrlist = []
            tokendriver.close()
            tokenLock.release()

        def interdata(url, datanum):
            # 打开Internal交易，获取数据，存放在列表中
            interdriver = webdriver.Edge(options=app.options, service=app.service)
            addnum = 0
            interdriver.get('https://' + url + '/txsInternal?a=' + wallet + '&ps=100&p=1')
            try:

                page = interdriver.find_element(By.XPATH,
                                                '//*[@id="ContentPlaceHolder1_divTopPagination"]/nav/ul/li[3]/span/strong[2]').text

            except:
                page = 1
                pass
            try:
                total = interdriver.find_element(By.XPATH, '//*[@id="ContentPlaceHolder1_divTopPagination"]/p').text
                total = int(total.split()[3])
            except:
                total = 0
                pass
            loadtext[wallet][url]['intertxsnum'] = total
            print(total, page)
            interLock.acquire()
            for number in range(1, int(page) + 1):
                if addnum < total - datanum:
                    interdriver.get('https://' + url + '/txsInternal?a=' + wallet + '&ps=100&p=' + str(number))
                    for pagenum in range(1, 101):
                        if addnum < total - datanum:
                            try:
                                href = interdriver.find_element(By.XPATH,
                                                                '//*[@id="ctl00"]/div[3]/div[2]/table/tbody/tr[' + str(
                                                                    pagenum) + ']/td[4]/span/a')

                                value = interdriver.find_element(By.XPATH,
                                                                 '//*[@id="ctl00"]/div[3]/div[2]/table/tbody/tr[' + str(
                                                                     pagenum) + ']/td[9]').text

                            except:
                                href = interdriver.find_element(By.XPATH,
                                                                '//*[@id="ctl00"]/div[3]/div[2]/table/tbody/tr/td[4]/span/a')
                                value = interdriver.find_element(By.XPATH,
                                                                 '//*[@id="ctl00"]/div[3]/div[2]/table/tbody/tr/td[9]').text
                                pass
                            app.intertokenlist.append(value.split(' ')[-1])
                            app.interhreflist.append(href.get_attribute('href'))
                            value = float(value.split(' ')[0].replace(',', ''))
                            app.intervaluelist.append(value)
                            addnum += 1
                        else:
                            break

                else:
                    break

            n = 0
            for href in app.interhreflist:
                interdriver.get(href)
                html = interdriver.find_element(By.XPATH, '/html').text
                projectset = func(html)
                # try:
                #     if url == 'etherscan.io':
                #         action = interdriver.find_element(By.ID,
                #                                           'wrapperContent').text
                #     else:
                #         action = interdriver.find_element(By.ID,
                #                                           'wrapperContent').text
                # except:
                #     action=''
                #     pass
                # timestamp = interdriver.find_element(By.ID, 'ContentPlaceHolder1_divTimeStamp').text.split('ago')[-1]
                # action = action + timestamp
                if projectset:
                    for xm in projectset:
                        project = xm + app.intertokenlist[n]
                        if project not in loadtext[wallet][url]['project']:
                            loadtext[wallet][url]['project'][project] = {'entry': 0, 'exit': 0, 'fee': 0,
                                                                         'token': app.intertokenlist[n],
                                                                         'action': {'IN': {}, 'OUT': {}}}
                        loadtext[wallet][url]['project'][project]['exit'] = loadtext[wallet][url]['project'][project][
                                                                                'exit'] + app.intervaluelist[n]/len(projectset)
                        # loadtext[wallet][url]['project'][project]['action']['IN'][action] = href
                n += 1
            app.interhreflist = []
            app.intervaluelist = []
            app.intertokenlist = []
            app.interfeelist = []
            interdriver.close()
            interLock.release()

        def txsdata(url, datanum):
            # 打开txs交易，获取数据，存放在列表中
            txsdriver = webdriver.Edge(options=app.options, service=app.service)
            addnum = 0

            txsdriver.get('https://' + url + '/txs?a=' + wallet + '&ps=100&p=1')
            try:
                page = txsdriver.find_element(By.XPATH,
                                              '//*[@id="ContentPlaceHolder1_topPageDiv"]/nav/ul/li[3]/span/strong[2]').text
            except:
                page = 1
                pass
            try:
                total = txsdriver.find_element(By.XPATH, '//*[@id="ContentPlaceHolder1_topPageDiv"]/p').text

                total = int(total.split()[3])

            except:
                total = 0
                pass
            loadtext[wallet][url]['txsnum'] = total
            print(total, page)
            txsLock.acquire()
            for number in range(1, int(page) + 1):

                if addnum < total - datanum:

                    txsdriver.get('https://' + url + '/txs?a=' + wallet + '&ps=100&p=' + str(number))
                    for pagenum in range(1, 101):
                        if addnum < total - datanum:

                            try:
                                href = txsdriver.find_element(By.XPATH,
                                                              '//*[@id="paywall_mask"]/table/tbody/tr[' + str(
                                                                  pagenum) + ']/td[2]/span/a')
                            except:
                                href = txsdriver.find_element(By.XPATH,
                                                              '//*[@id="paywall_mask"]/table/tbody/tr[' + str(
                                                                  pagenum) + ']/td[2]/span[2]/a')
                                pass
                            app.txshreflist.append(href.get_attribute('href'))
                            method = txsdriver.find_element(By.XPATH,
                                                            '//*[@id="paywall_mask"]/table/tbody/tr[' + str(
                                                                pagenum) + ']/td[3]').text

                            app.methodlist.append(method)
                            cr = txsdriver.find_element(By.XPATH,
                                                        '//*[@id="paywall_mask"]/table/tbody/tr[' + str(
                                                            pagenum) + ']/td[8]').text
                            value = txsdriver.find_element(By.XPATH,
                                                           '//*[@id="paywall_mask"]/table/tbody/tr[' + str(
                                                               pagenum) + ']/td[10]').text
                            app.txstokenlist.append(value.split(' ')[-1])
                            fee = txsdriver.find_element(By.XPATH,
                                                         '//*[@id="paywall_mask"]/table/tbody/tr[' + str(
                                                             pagenum) + ']/td[11]').text
                            if cr != 'OUT':
                                value = float(value.split(' ')[0].replace(',', ''))
                                app.txsfeelist.append(0)
                            else:
                                value = -float(value.split(' ')[0].replace(',', ''))
                                app.txsfeelist.append(float(fee))
                            app.txsvaluelist.append(value)
                            addnum += 1
                        else:
                            break
                else:
                    break

            n = 0
            for href in app.txshreflist:
                txsdriver.get(href)
                html = txsdriver.find_element(By.XPATH, '/html').text
                projectset = func(html)
                if not projectset:
                    project = app.methodlist[n]
                    projectset.add(project)
                for xm in projectset:
                    project = xm + app.txstokenlist[n]
                    if project not in loadtext[wallet][url]['project']:
                        loadtext[wallet][url]['project'][project] = {'entry': 0, 'exit': 0, 'fee': 0,
                                                                     'token': app.txstokenlist[n],
                                                                     'action': {'IN': {}, 'OUT': {}}}
                    if app.txsvaluelist[n] > 0:
                        # action = txsdriver.find_element(By.XPATH, '//*[@id="ContentPlaceHolder1_maintable"]/div[5]').text
                        loadtext[wallet][url]['project'][project]['exit'] = loadtext[wallet][url]['project'][project][
                                                                                'exit'] + app.txsvaluelist[n]/len(projectset)

                    else:
                        # action = txsdriver.find_element(By.XPATH, '//*[@id="ContentPlaceHolder1_maintable"]/div[6]').text
                        loadtext[wallet][url]['project'][project]['entry'] = loadtext[wallet][url]['project'][project][
                                                                                 'entry'] - app.txsvaluelist[n]/len(projectset)

                    loadtext[wallet][url]['project'][project]['fee'] = loadtext[wallet][url]['project'][project]['fee'] + \
                                                                       app.txsfeelist[n]/len(projectset)
                n += 1
                print(n)
            app.txshreflist = []
            app.txsvaluelist = []
            app.txstokenlist = []
            app.txsfeelist = []
            app.methodlist = []
            txsdriver.close()
            txsLock.release()

        for key in loadtext[wallet]:
            thread1 = TokenThread(key, loadtext[wallet][key]['token20num'])
            thread1.start()
            thread2 = InterThread(key, loadtext[wallet][key]['intertxsnum'])
            thread2.start()
            thread3 = TxsThread(key, loadtext[wallet][key]['txsnum'])
            thread3.start()
            threadlist.extend([thread1,thread2,thread3])
        for t in threadlist:
            t.join()
        fp.seek(0)
        json.dump(loadtext, fp)
        return render_template('wallet.html', result1=loadtext[wallet]["bscscan.com"]['project'],
                               result2=loadtext[wallet]["etherscan.io"]['project'],totaltokenvalue1=loadtext[wallet]["etherscan.io"]['totaltokenvalue'],totaltokenvalue2=loadtext[wallet]["bscscan.com"]['totaltokenvalue'],totalvalue1=loadtext[wallet]["etherscan.io"]['totalvalue'],totalvalue2=loadtext[wallet]["bscscan.com"]['totalvalue'])


if __name__ == '__main__':
    app.run(host='127.0.0.2', port=3090, debug=True)
