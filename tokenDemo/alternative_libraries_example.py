from curl_cffi import requests
url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
params = {
    "fields1": "f1,f2,f3,f4,f5,f6",
    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
    "ut": "7eea3edcaed734bea9cbfc24409ed989",
    "klt": "101",
    "fqt": "1",
    "secid": "0.002326",
    "beg": "20251111",
    "end": "20251117",
}
r = requests.get(url, params=params, timeout=5,impersonate="chrome110")
data_json = r.json()
print(data_json)