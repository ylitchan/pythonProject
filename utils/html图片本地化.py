# @Date: 2024/7/29
# @Author: ylitchan
# @Source: rdti_crawl_defense
# @Site:
import io
import uuid

from PIL import Image
from curl_cffi import requests
from lxml import etree

PROXY = 'http://192.168.8.42:10502'
PROXIES = {
    "http": PROXY,
    "https": PROXY
}
session = requests.Session()
session.impersonate = 'chrome110'
# session.proxies = PROXIES
session.verify = False
session.timeout = 1
session.headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36', }
import os

# 指定目录
directory = r'D:/pythonProject/utils/zy'

# 获取目录中的所有文件和文件夹
all_files_and_folders = os.listdir(directory)

# 过滤出所有文件
files = [f for f in all_files_and_folders if os.path.isfile(os.path.join(directory, f))]

# 打印所有文件
for file in files:
    print(file)
    # 读取HTML文件内容
    with open(os.path.join(directory, file), 'r', encoding='utf-8') as f:
        html_content = f.read()
    # 使用lxml解析HTML内容
    parser = etree.HTMLParser()
    tree = etree.fromstring(html_content, parser)
    try:
        img_tags = tree.xpath('//img')
    except:
        continue
    # 修改所有img标签的src属性
    for img_tag in img_tags:
        for j in img_tag.attrib.values():
            if j.startswith('http'):
                try:
                    res = session.get(j.split(' ')[0])
                    res.raise_for_status()
                    img_io = io.BytesIO(res.content)
                    img = Image.open(img_io)
                    img.verify()
                    # 获取图像格式
                    img_format = img.format.lower()
                    # 生成保存路径
                    # 生成一个随机UUID
                    random_uuid = uuid.uuid1()
                    img_path = f'{random_uuid}.{img_format}'
                    save_path = os.path.join(f"./{directory.split('/')[-1]}/bd/img/", img_path)
                    # 保存图像到本地
                    Image.open(img_io).save(save_path)
                    img_tag.set('src', os.path.join("./img", img_path))
                    break
                except:
                    continue
    # 将修改后的HTML内容写回文件
    modified_html = etree.tostring(tree, pretty_print=True, method="html", encoding='unicode')
    with open(os.path.join(directory + "/bd", file), 'w', encoding='utf-8') as f:
        f.write(modified_html)
