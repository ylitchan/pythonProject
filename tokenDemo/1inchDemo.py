import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from pydantic.schema import datetime

url = "https://proxy-app.1inch.io/v2.0/v1.5/chain/1/router/v6/quotes"

params = {
    'fromTokenAddress': "0x97de57ec338ab5d51557da3434828c5dbfada371",
    'toTokenAddress': "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    'amount': "1000000000000000000",
    'gasPrice': "781262402",
    'preset': "maxReturnResult",
    'walletAddress': "0x0000000000000000000000000000000000000000"
}

headers = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0",
    'Accept': "application/json, text/plain, */*",
    'Accept-Encoding': "gzip, deflate, br, zstd",
    'sec-ch-ua-platform': "\"Windows\"",
    'authorization': "Bearer eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbiI6IjVjODg5ODA0LTA4YmMtNDZmYi05MmI5LWYwZjZiYzQxOTQyMyIsImV4cCI6MTc0MDkyNTg2NSwiZGV2aWNlIjoiYnJvd3NlciIsImlhdCI6MTc0MDkyMjI2NX0.d0VvW1hWkEOKrb0SZuykeOVB9hzPi2yCoMT4TuLt5bQrUFQqdKatWG5-ChuhZ7AFROZ-_j4d3oLfLmP9Z3-8Ig",
    'x-user-id': "10b64809-34aa-4e7b-9094-c4d942e852bc",
    'sec-ch-ua': "\"Not(A:Brand\";v=\"99\", \"Microsoft Edge\";v=\"133\", \"Chromium\";v=\"133\"",
    'sec-ch-ua-mobile': "?0",
    'x-session-id': "d5bff7d4-7037-4850-a9af-8b4071554148",
    'origin': "https://app.1inch.io",
    'sec-fetch-site': "same-site",
    'sec-fetch-mode': "cors",
    'sec-fetch-dest': "empty",
    'referer': "https://app.1inch.io/",
    'accept-language': "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    'priority': "u=1, i",
    'Cookie': "__cf_bm=JYlWaTT8rgHhCVgEzvGOvNxc3EuZXQpOVXne9gbCJi4-1740922259-1.0.1.1-1p8SIVpPgyFPMYngHPTid91VEzMiiBpZvDNUPBdJ1y7va0_1qkekAv5QjX01raVskg0JI1rISfXg.B3ye0qNjfXNz1CTuOIzoZKiJXePbtY; cf_clearance=gs5utlyDeLdYWebpZY5.2.eNWA7Crrq9vMG3s5ZZy9Q-1740922263-1.2.1.1-OcWszmKGMQSxJ.dnC1r4M.MEQ1pw9CYCerbIuLerWWYWpsmOTlyM9jhx34zA_10nrR8Gjov_lpDPhZ1znVSCw2ope3Bf2RZXVX5GaxqyFTh0sb8Cik2FZFUtmrRoyiweNJhlTBDWmkR6sBeE29Vsp0RdhZQm5yPbKlcvZzjuoVFFLKVgLqVQYtzZX_mzxoWtZ_TWhRv6sMRrh5bGWEzLJ3.qMuY_ymcclyf67508sa5EHt6KJqNhXN6DOhmV6vvmt4nd7TXSI.yt9pYFDw.WUtyMPb8lzfplDzRPy0dLbnWnTOoS0YNEjqYnqZM2auta6W_X1MEe_5qNMCPgoeuhm60DUSxU.yyAhT0uijL86jDuY_J207XQAZxK4OQlWy5tECf1be_pZdJEzJu3ZKM9ZWOvrTR5H1yxCn70TSb1AV0; _gcl_au=1.1.1888060563.1740922273; _ga=GA1.1.1438687851.1740922273; _ga_9D763FF898=GS1.1.1740922272.1.0.1740922272.60.0.0; _tt_enable_cookie=1; _ttp=01JNBGVFTGH1N8N1RSSHNWNX9Y_.tt.1; mp_c0937a84b4e3e4f191c04ff7d0d24ad3_mixpanel=%7B%22distinct_id%22%3A%20%22%24device%3A195570dc0043b58-02e5c44244f84b-4c657b58-240000-195570dc0043b58%22%2C%22%24device_id%22%3A%20%22195570dc0043b58-02e5c44244f84b-4c657b58-240000-195570dc0043b58%22%2C%22%24initial_referrer%22%3A%20%22%24direct%22%2C%22%24initial_referring_domain%22%3A%20%22%24direct%22%7D"
}


def send_msg(msg):
    try:
        print(msg)
        json_msg = {
            "msgtype": "text",
            "text": {'content': msg}
        }
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=ee6e64f7-4423-47d0-9f9c-583298d7ae02',
            json=json_msg)
    except:
        return


def get_price():
    response = requests.get(url, params=params, headers=headers)
    assetPrice = float(response.json()['bestResult']['toTokenAmount']) / 10e5
    print(datetime.now(), assetPrice)
    if assetPrice <= 1.05:
        send_msg(f'eUSD V1价格{assetPrice}')


if __name__ == "__main__":
    session = requests.Session()
    session.verify = False
    session.headers = {'Content-Type': 'application/json'}
    # 创建BlockingScheduler对象
    scheduler = BlockingScheduler()
    scheduler.add_job(get_price, 'cron', hour='*', minute='*/5', second='00', timezone='Asia/Shanghai')
    get_price()
    # 启动调度器
    scheduler.start()
