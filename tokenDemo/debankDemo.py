import json
from datetime import datetime

from curl_cffi import requests

url = "https://api.debank.com/portfolio/project_list"

params = {
    'user_addr': "0x2ec65b1c8ddd841b025ee3d134015ae907ba1a73"
}

headers = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
    'Accept-Encoding': "gzip, deflate, br, zstd",
    'pragma': "no-cache",
    'cache-control': "no-cache",
    'sec-ch-ua-platform': "\"Windows\"",
    'account': "{\"random_at\":1744602342,\"random_id\":\"0480933ec4d24e31bbd3a95a0234e443\",\"user_addr\":null}",
    'x-api-ver': "v2",
    'sec-ch-ua': "\"Microsoft Edge\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
    'sec-ch-ua-mobile': "?0",
    'source': "web",
    'x-api-sign': "eeb8e58a47c898683ba334b56dcaa32f343b741283367b69cb0ddbcbdeddb4f9",
    'x-api-nonce': "n_VipbdhG4IvfzIEwvgJ9KJvGvh7tLXcuVcKMU9QOw",
    'x-api-ts': "1744610654",
    'origin': "https://debank.com",
    'sec-fetch-site': "same-site",
    'sec-fetch-mode': "cors",
    'sec-fetch-dest': "empty",
    'referer': "https://debank.com/",
    'accept-language': "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    'dnt': "1",
    'sec-gpc': "1",
    'priority': "u=1, i"
}
response = requests.get(url, params=params, headers=headers, impersonate='chrome110')
data = response.json()['data'][-1]['portfolio_item_list']
farming = {}
vesting = {}
farming['rewards'] = '\n'.join([f'{rt["name"]}:{rt["amount"]}' for rt in data[0]['detail']['reward_token_list']])
farming['usdValue'] = data[0]['stats']['net_usd_value']
vesting['pool'] = data[-1]['detail']['token']['name']
vesting['balance'] = data[-1]['detail']['token']['amount']
vesting['claimable_amount'] = data[-1]['detail']['token']['claimable_amount']
# 转换为本地时间（结构化时间 struct_time）
local_time = datetime.fromtimestamp(data[-1]['detail']['end_at'])
# 格式化为字符串
vesting['end_time'] = local_time.strftime("%Y/%m/%d %H:%M:%S")
vesting['usdValue'] = data[-1]['stats']['net_usd_value']
msg = f'Farming:\n{json.dumps(farming, ensure_ascii=False, indent=4)}\n-------\nVesting:\n{json.dumps(vesting, ensure_ascii=False, indent=4)}'
print(msg)
