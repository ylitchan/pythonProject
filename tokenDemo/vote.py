import requests
from flask import Flask, request
from flask_cors import CORS
from lxml import etree

app = Flask(__name__)
# 设置请求体最大为 16MB
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 16 MB
CORS(app, supports_credentials=True)
requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.verify = False
session.headers = {'Content-Type': 'application/json',
                   'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'}


@app.route('/', methods=['POST'])
def receive_html():
    html_data = request.form.get('html')
    if html_data:
        alert = []
        alert0 = []
        print("Received HTML content:")
        tree = etree.HTML(html_data)

        # 这里写提取数据的代码

        links = tree.xpath('//div[@class="css-1dveyv5"]')
        for link in links:
            content = link.xpath('.//div[@class="css-zxi8en"]//text()')
            symbol = content[0]
            voter = float(content[1].split('%')[0] if '%' in content[1] else '0')
            bribe = float(content[2].split('%')[0] if '%' in content[2] else '0')
            if bribe:
                alert.append((symbol, voter, bribe, voter + bribe))
            else:
                alert0.append((symbol, voter, bribe, voter + bribe))
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
        return 'HTML received successfully', 200
    else:
        return 'No HTML data provided', 400


if __name__ == '__main__':
    html_data = ''
    alert = []
    alert0 = []
    print("Received HTML content:")
    tree = etree.HTML(html_data)

    # 这里写提取数据的代码

    links = tree.xpath('//div[@class="css-1dveyv5"]')
    for link in links:
        content = link.xpath('.//div[@class="css-zxi8en"]//text()')
        symbol = content[0]
        voter = float(content[1].split('%')[0] if '%' in content[1] else '0')
        bribe = float(content[2].split('%')[0] if '%' in content[2] else '0')
        if bribe:
            alert.append((symbol, voter, bribe, voter + bribe))
        else:
            alert0.append((symbol, voter, bribe, voter + bribe))
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
    app.run(host='0.0.0.0', port=9000, debug=False)
