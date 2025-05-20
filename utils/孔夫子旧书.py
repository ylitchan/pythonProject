import time

import pandas as pd
import requests

df = pd.read_excel('D:\pythonProject\副本副本2025-5-16厦大社未缴送1269种-12.xlsx')
shu = df.iloc[520:580, [2, 4]]
# shu = [i.replace('—', '').replace('·', '').replace('：', '').split('（')[0].split('(')[0].split('.')[0] for i in shu]
url = "https://search.kongfz.com/pc-gw/search-web/client/pc/product/keyword/list"
headers = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
    'Accept': "application/json, text/plain, */*",
    'Accept-Encoding': "gzip, deflate, br, zstd",
    'Pragma': "no-cache",
    'Cache-Control': "no-cache",
    'sec-ch-ua-platform': "\"Windows\"",
    'sec-ch-ua': "\"Chromium\";v=\"136\", \"Microsoft Edge\";v=\"136\", \"Not.A/Brand\";v=\"99\"",
    'sec-ch-ua-mobile': "?0",
    'Sec-Fetch-Site': "same-origin",
    'Sec-Fetch-Mode': "cors",
    'Sec-Fetch-Dest': "empty",
    'Referer': "https://search.kongfz.com/product/?dataType=0&keyword=%E4%BA%BA%E6%96%87%E6%AD%A6%E5%A4%B7%EF%BC%9A%E9%BA%BB%E7%B2%9F%E6%98%9F%E7%A9%BA&page=1",
    'Accept-Language': "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    'dnt': "1",
    'sec-gpc': "1",
    'Cookie': "shoppingCartSessionId=8f2767982bc6a7402c9fce46221ba679; kfz_uuid=911fd501-da9e-4bd9-abd8-0217e6aabb4f; PHPSESSID=a8aec41cba4e66f06acc68e56d9b20d378c3b536; reciever_area=1001000000; kfz_trace=911fd501-da9e-4bd9-abd8-0217e6aabb4f|23327820|8cd9f41080ae7f9f|-"
}
results = []
for s in shu.itertuples():
    print(s[2])
    params = {
        'dataType': "0",
        'keyword': s[2].replace('—', '').replace('·', '').replace('：', '').split('（')[0].split('(')[0].split('.')[0],
        'page': "1",
        'press': "厦门大学出版社",
        'actionPath': "press",
        'userArea': "1001000000"
    }
    while True:
        try:
            response = requests.get(url, params=params, headers=headers)
            data = response.json()['data']['itemResponse']['list']
            if data:
                for d in data:
                    if d['isbn'].strip() and d['isbn'].strip()[:-1] == s[1].replace('-', '').strip()[:-1]:
                        dd = {'标题': s[2], '题名': d['title'], '厦大ISBN': s[1], 'ISBN': d['isbn'].strip(),
                              '价格': d['price'],
                              '链接': d['link']['pc']}
                        results.append(dd)
                        print(dd)
                    elif not d['isbn'].strip():
                        dd = {'标题': s[2], '题名': d['title'], '厦大ISBN': s[1], 'ISBN': '无', '价格': d['price'],
                              '链接': d['link']['pc']}
                        results.append(dd)
            else:
                dd = {'标题': s[2], '题名': '无', '厦大ISBN': s[1], 'ISBN': '无', '价格': '无', '链接': '无'}
                results.append(dd)
                print(dd)
            time.sleep(3)
            break
        except:
            time.sleep(3)
print(results)
pd.DataFrame(results).to_excel('厦大书籍.xlsx')
