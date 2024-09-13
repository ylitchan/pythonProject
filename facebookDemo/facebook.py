import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from curl_cffi import requests
from fastapi import FastAPI
from jsonpath_ng.parser import parse

# 创建 FastAPI 实例
app = FastAPI()
mem = []
executor = ThreadPoolExecutor()
thread_pool = ThreadPoolExecutor(max_workers=100)


def get_contact(k, v):
    res = requests.get(f'{v}/about_contact_and_basic_info', impersonate='chrome110', headers=
    {
        "Reqable-Id": "",
        "Host": "",
        "User-Agent": "Reqable/2.22.0",
        "Connection": "keep-alive",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Cookie": "c_user=100091673057038; fr=1j9nxOQxvPOKX4sXj.AWXaOs8fh0R1Ek8TUjXmBMfAvXw.Bmz_18..AAA.0.0.Bmz_18.AWUHtOpI_FQ; xs=14%3ApNP1rc_LM_VU5A%3A2%3A1724902727%3A-1%3A-1%3A%3AAcWgPaKegtbHybbQ2Rsg9AtDkUXtGKEu6QqvXZu7NA",
        "cache-control": "max-age=0",
        "dpr": "1.25",
        "viewport-width": "845",
        "sec-ch-ua": "\"Chromium\";v=\"128\", \"Not;A=Brand\";v=\"24\", \"Microsoft Edge\";v=\"128\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-ch-ua-platform-version": "\"10.0.0\"",
        "sec-ch-ua-model": "\"\"",
        "sec-ch-ua-full-version-list": "\"Chromium\";v=\"128.0.6613.85\", \"Not;A=Brand\";v=\"24.0.0.0\", \"Microsoft Edge\";v=\"128.0.2739.42\"",
        "sec-ch-prefers-color-scheme": "light",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "navigate",
        "sec-fetch-user": "?1",
        "sec-fetch-dest": "document",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "cookie": "presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1724919207506%2C%22v%22%3A1%7D",
        "dnt": "1",
        "sec-gpc": "1",
        "priority": "u=0, i"
    })
    if email := re.findall('''"websites_and_social_links".*?"text":"(.*?)"},''', res.content.decode(),
                           re.S):
        email = email[0].replace('\\\\', '\\').encode().decode('unicode_escape')
        if '@' in email:
            d = {'email': email, 'name': k, 'url': v}
            print(d)
            mem.append(d)


def job(data):
    data = json.loads(data['data'])
    data = parse('data.node.new_members.edges').find(data)[0].value
    data = dict(zip([i.value for i in parse('$..node.name').find(data)],
                    [i.value for i in parse('$..node.url').find(data)]))
    futures = [thread_pool.submit(get_contact, k, v) for k, v in data.items()]
    as_completed(futures)


# 定义一个 POST 请求接口，用于创建用户
@app.post("/reqable/")
async def reqable(data: dict):
    # 在这里可以处理用户数据，例如存储到数据库
    futures = [thread_pool.submit(job, data)]
    as_completed(futures)
    return


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
