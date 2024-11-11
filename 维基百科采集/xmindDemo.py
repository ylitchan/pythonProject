import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pinyin
import requests
import wikipedia
from lxml import etree
from pygtrans import Null
from xmindparser import xmind_to_dict

from utils.翻译 import translate

os.environ['http_proxy'] = 'http://127.0.0.1:7890'
os.environ['https_proxy'] = 'http://127.0.0.1:7890'


def extract_first_letters(text):
    pinyin_str = pinyin.get_initial(text, delimiter='')
    return pinyin_str


def parse_xmind_to_paths(file_path):
    # 解析XMind文件
    xmind_data = xmind_to_dict(file_path)

    paths = []

    def extract_paths(topic, current_path):
        # 将当前节点的标题添加到路径中
        current_path.append(topic.get("title"))

        # 如果没有子节点，则将当前路径添加到结果中
        if "topics" not in topic or not topic["topics"]:
            paths.append(list(current_path))
            # 回溯：移除当前节点的标题
            current_path.pop()
            return paths

        else:
            # paths.append(list(current_path))
            # 递归处理每个子节点
            for sub_topic in topic["topics"]:
                extract_paths(sub_topic, current_path)

        # 回溯：移除当前节点的标题
        current_path.pop()

    # 处理XMind文件的第一个工作簿和第一个工作表
    first_sheet = xmind_data[0]["topic"]["topics"][0]["topics"][0]["topics"][0]
    extract_paths(first_sheet, [])
    import pandas as pd

    # 列表的列表，子列表长度不一，元素都是值
    data = paths
    for p in paths:
        for i, pp in enumerate(p):
            if i == 0:
                p[i] = pp.split('l')[0].replace('l', 'l')
            elif pp_s := re.search('[-\dA-Z]+', pp):
                pp_ss = pp_s.group()
                if pp_ss in extract_first_letters(pp.replace(pp_ss, '')).upper():
                    p[i] = pp.replace(pp_ss, '')
    # 将每个子列表转换为 Series，并组合成一个 DataFrame
    df = pd.DataFrame([pd.Series(x) for x in data])

    # 指定要写入的 Excel 文件名
    excel_file = 'l.xlsx'

    # 将数据写入 Excel 文件
    df.to_excel(excel_file, index=False, header=False)

    print(f'Data has been written to {excel_file}')
    return paths


def get_html(path):
    if len(path) <= 3:
        return
    # print(path)
    # kw = path[1][:2] + ';' + ';'.join(path[3:])
    kw = path[1][:2] + ';' + path[-1]
    if '俄罗;' in kw:
        kw = kw.replace('俄罗;', '俄罗斯;')
    # print(kw)
    kw_t = translate(kw, target='en')
    if isinstance(kw_t, Null):
        kw_t = kw
    try:
        url = wikipedia.page(kw_t).url
        res = requests.get(url)
        res.raise_for_status()
        parser = etree.HTMLParser()
        tree = etree.fromstring(res.content, parser)
        title = ''.join(tree.xpath('//*[@id="firstHeading"]//text()'))
        # print(title, kw_t)
        if not contains_any(kw_t, title, res.text):
            no_result.append(path)
            return
        abs_fold = os.path.join(r'G:\维基百科', '\\'.join(path[:-1]).replace('/', '&'))
        if not os.path.exists(abs_fold):
            os.makedirs(abs_fold)
        with open(os.path.join(abs_fold, f"{path[-1]}.html"), 'wb') as file:
            file.write(res.content)
    except Exception as e:
        no_result.append(path)
        print(path, '采集失败', str(e))


def contains_any(keyword, title, content):
    keyword = keyword.lower()
    title = title.lower()
    content = content.lower()

    # 用 ';' 切割字符串 a
    substrings = keyword.split(';')
    if len(substrings) == 2:
        substring = substrings[-1]
        # 检查 title 和 content 是否包含切割后的最后一个子字符串
        if substring in title or substring in content:
            return True
    return False


if __name__ == '__main__':
    # 使用示例
    file_path = 'D:\pythonProject\维基百科采集\l.xmind'
    parsed_paths = parse_xmind_to_paths(file_path)
    no_result = []
    thread_pool = ThreadPoolExecutor(max_workers=10)
    # self.get_baidu_info(lists[1])
    futures = [thread_pool.submit(get_html, path) for path in parsed_paths]
    # 使用as_completed方法来获取已完成的任务
    for future in as_completed(futures):
        result_info = future.result()
    thread_pool.shutdown()
    # for path in parsed_paths:
    #     print(path)
    #     get_html(path)
    print('无结果：', no_result)
