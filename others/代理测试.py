# coding=utf-8
import requests

#
# 请求地址 简单提取 具体需要根据实际情况获取 记得添加白名单 http://www.siyetian.com/member/whitelist.html
tiquApiUrl = 'http://proxy.siyetian.com/apis_get.html?token=gHbi1yTEFFNPRUVz8ERBVjTB1STqFUeNpWR31keFhnTU1kMOpWV65kaNBTTqNWe.AM5QDO1QzN2YTM&limit=1&type=0&time=10&split=1&split_text=&area=0&repeat=0&isp=0'
apiRes = requests.get(tiquApiUrl, timeout=5)
# 代理服务器
ipport = apiRes.text

# 要访问的网站链接
url = "https://opensea.io/zh-CN"  # 例如百度
proxies = {
    'http': ipport,
    'https': ipport
}
res = requests.get(url, proxies={
    'http': 'http://112.66.252.75:14753',
    'https': 'http://112.66.252.75:14753'
}, timeout=5)
print(res.status_code)
print(res.text)
