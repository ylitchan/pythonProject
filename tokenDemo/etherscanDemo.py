import requests
from lxml import etree

url = "https://etherscan.io/txs"
headers = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0",
    'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    'Accept-Encoding': "gzip, deflate, br, zstd",
    'cache-control': "max-age=0",
    'sec-ch-ua': "\"Not(A:Brand\";v=\"99\", \"Microsoft Edge\";v=\"133\", \"Chromium\";v=\"133\"",
    'sec-ch-ua-mobile': "?0",
    'sec-ch-ua-full-version': "\"133.0.3065.82\"",
    'sec-ch-ua-arch': "\"x86\"",
    'sec-ch-ua-platform': "\"Windows\"",
    'sec-ch-ua-platform-version': "\"19.0.0\"",
    'sec-ch-ua-model': "\"\"",
    'sec-ch-ua-bitness': "\"64\"",
    'sec-ch-ua-full-version-list': "\"Not(A:Brand\";v=\"99.0.0.0\", \"Microsoft Edge\";v=\"133.0.3065.82\", \"Chromium\";v=\"133.0.6943.127\"",
    'upgrade-insecure-requests': "1",
    'sec-fetch-site': "same-origin",
    'sec-fetch-mode': "navigate",
    'sec-fetch-user': "?1",
    'sec-fetch-dest': "document",
    'referer': "https://etherscan.io/txs?a=0xa980d4c0c2e48d305b582aa439a3575e3de06f0e&p=97",
    'accept-language': "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    'priority': "u=0, i",
    'Cookie': "etherscan_offset_datetime=+8; etherscan_switch_token_amount_value=value; cards-currentTab=all; _ga=GA1.1.412262204.1739630033; ASP.NET_SessionId=ou5vv50ss4wvyjfhlbs3qedk; __cflb=02DiuFnsSsHWYH8WqVXcJWaecAw5gpnmem4CT7U2HnBYp; _ga_T1JC9RNQXV=GS1.1.1740740334.31.1.1740744162.58.0.0; cf_clearance=m8M4_JP72Zy8Q8cyP.Kk.QLTW1qeZA_RG6PznjEW.xc-1740744163-1.2.1.1-rsCZhLZtxDQuu3fXVkGXg2co2jwHr5Q9B2SfIc0MwnbgmJg1U4uNQlc8WGM.6bYj_pOQJrKzKHbClHfhNf2wnXFG8h0e86ahRKn0PHoOBrWO9Q8TwohlFCNRQUmsLfpxZtOqPykuGiOKuYvz3yfxSBUjZCJ5xYEDtUArAkx6VCbczthBSN8EiAQCTIouhJyFxL1YD6AnEA.eu9uTd5fCZdHgvFzG5bvkm98VFEzR6Tutvma9VPBz53Qk1bZqJgeNE3PRlMGKlYohELmRR3vj2UOojuHhb2Ir6yT3bLGKgkM"
}
address=set()
for p in range(1, 98):
    print(p)
    while 1:
        try:
            params = {
                'a': "0xa980d4c0c2e48d305b582aa439a3575e3de06f0e",
                'p': str(p)
            }
            response = requests.get(url, params=params, headers=headers)
            selector = etree.HTML(response.text)
            address.update([i for i in selector.xpath('//tr[contains(.//@data-title,"Deposit")]//@data-highlight-target') if
                       i != '0xa980d4c0C2E48d305b582AA439a3575e3de06f0E'])
            break
        except:
            continue
print(55)
