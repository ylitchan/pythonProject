"""
@Project :   rtdi-data-center
@File    :   knowfar_usa.py
@Time    :   2024/5/11 下午4:12
@Author  :   lwxie
@Desc    :   知远 条令法规
"""
import random
import re
import time

import requests
from bs4 import BeautifulSoup
from lxml import etree
from pygtrans import Translate, Null
from requests.adapters import HTTPAdapter
from urllib3 import Retry

PROXIES = {}


def translate(text: str, target: str = 'zh-CN', source: str = 'auto'):
    """
    字符串翻译：目前主要用于外语中时间的翻译
    :param text: 待翻译文本
    :param target: 翻译目标语言
    :param source: 源语言
    :return:
    """
    try:
        if not text:
            return text
        client = Translate(target=target, source=source, proxies=PROXIES)
        content = client.translate(text)
        size = 0
        while isinstance(content, Null) and size < 3:
            size += 1
            content = client.translate(text, source=source)
        if isinstance(content, Null):
            # 翻译失败
            return text
        content_tran = content.translatedText
        if isinstance(content_tran, list):
            return content_tran[0]
        return content_tran
    except Exception as e:
        print(f"google tran error: {e}")
        return ""


def run_sleep_uniform(min_time, max_time, is_print=False):
    """
    自定义随机暂停
    :param min_time: 最小时间单位秒
    :param max_time: 最大时间单位秒
    :param is_print: 是否打印
    :return:
    """
    rand_value = round(random.uniform(min_time, max_time), 2)
    time.sleep(rand_value)


class KnowfarTiaoLing:

    def __init__(self) -> None:
        self.country = None
        self.arms = None
        self.type = None
        self.subtype = None
        self.number = None
        self.title = None
        self.title_link = None
        self.release_date = None
        # 标题（译）
        self.title_zh = None
        # 内部编号
        self.internal_number = None
        # 国家/地区
        self.country_region = None
        # 职能领域
        self.functional_areas = None
        # 职能领域子分类
        self.functional_areas_sub = None
        # 军种/部门
        self.service_department = None
        # 分类
        self.classify = None
        # 二级分类
        self.two_classify = None
        # 责任部门
        self.responsible_department = None
        # 发布机构
        self.issuing_agency = None
        # 文件语言
        self.document_language = None
        # 关键词
        self.Key_words = None
        # 字数
        self.word_count = None
        # 页数
        self.page_count = None
        # 文件大小
        self.document_size = None
        # 摘要-英语
        self.summary_en = None
        # 摘要-中文
        self.summary_zh = None
        # 文件来源地址
        self.file_source_url = None


type_sub = []

cookies = {
    "cookies_identity": "d011c263318c427a96bcfb019aa5d49d",
    "ASP.NET_SessionId": "rxn4mqxz51jl0xs5q4bqhyaf"
}

headers = {
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    # 'Cookie': 'cookies_identity=9746b0df89fa4284bbd02c73d27e05b5; ASP.NET_SessionId=t4ofbdnrpko3f5frixiovzpr; Hm_lvt_0000ee273574f628bd5d882b772b4c97=1715412957; KnowfarData2023_user=id=10017972&userkey=f1a200e8&groupid=1&cookies=c18005623; Hm_lpvt_0000ee273574f628bd5d882b772b4c97=1715677700',
    'Referer': 'http://www.knowfar.net.cn/database/tiaoling/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest',
}

all_datas = []


def get_list(country, c_type, arms, subtype):
    for page in range(1, 53):
        params = {
            'oper': 'ajaxGetList',
            'topicid': '',
            'page': str(page),
            'channelid': '5',
            'haspaid': '',
            'isdemo': '',
            'country': country,
            'language': '',
            'type': c_type,
            'arms': arms,
            'subtype': subtype,
            'subtype2': '',
            'fight': '',
            'subfight': '',
            'year': '',
            'title': '',
            'k': '',
            'summary': '',
            'author': '',
            'org': '',
            'person': '',
            'publisher': '',
            'identifier': '',
            'tags': '',
            'if_title': '',
            'if_title_fen': '',
            'if_k': '',
            'if_summary': '',
            'if_author': '',
            'if_org': '',
            'if_publisher': '',
            'if_identifier': '',
            'if_tags': '',
            'parentid': '',
            'module': 'tiaoling',
            'moduleid': '112',
            'prefix': '',
            'type2': '',
            'type3': '',
            'type4': '',
            'type5': '',
            'type6': '',
            'type7': '',
            'translation_status': '',
            'fulltextlevel': '',
            'contenttype': '',
            'yearnumtype': '',
            'title_parent': '',
            'uid': '',
            'sortfield': 'publisher_full,date',
            'reverse': '0,1',
            'identifier_parent': '',
            'indexdeep': '1',
            'complete_matching': '',
        }

        response = request_get(
            f'http://www.knowfar.net.cn/search/ajax_search.aspx?oper=ajaxGetList&topicid=&page={page}&channelid=8&haspaid=&isdemo=&country=%E7%BE%8E%E5%9B%BD&language=&type=&arms=&subtype=&subtype2=&fight=&subfight=&year=&title=&k=&summary=&author=&org=&person=&publisher=&identifier=&tags=&if_title=&if_title_fen=&if_k=&if_summary=&if_author=&if_org=&if_publisher=&if_identifier=&if_tags=&parentid=&module=wj_journal&moduleid=115&prefix=&type2=&type3=&type4=&type5=&type6=&type7=&translation_status=&fulltextlevel=&contenttype=&yearnumtype=&title_parent=&uid=&sortfield=date&reverse=1&identifier_parent=&indexdeep=&complete_matching=',
            params)
        print(f'页数{str(page)}，状态：{response.status_code}')

        body_str = response.json()['body']
        if not body_str or '未检索到相关信息' in body_str:
            break
        soup = BeautifulSoup(body_str, 'html.parser')

        # 以 class="collect" 为界限切割 HTML 内容
        collect_divs = soup.find_all('div', class_='info')

        for collect_div in collect_divs:
            # 获取每个 collect_div 的父级 <tr> 元素
            tr_element = collect_div.find_parent('div')
            # 获取 <td> 下的 <span> 和 <a> 元素的文本值
            number = None
            title = None
            title_link = None
            release_date = None
            title_zh = None
            try:
                # number = tr_element.find('span', class_='number').get_text(strip=True)
                # spans = tr_element.find_all('span', class_='number')
                # number = ';'.join(span.get_text(strip=True) for span in spans)
                title = tr_element.find('a').get_text(strip=True)
                title_link = tr_element.find('a').get('href')
                # release_date = tr_element.find('td', class_='center').get_text(strip=True)
            except Exception as e:
                print('采集错误\n', str(e))

            ktl = KnowfarTiaoLing()
            ktl.country = country
            ktl.arms = arms
            ktl.type = c_type
            ktl.subtype = subtype
            ktl.title = title
            ktl.title_link = title_link
            # 请求详情
            get_detail(ktl)
            run_sleep_uniform(0.1, 1)

        # 请求随机暂停
        run_sleep_uniform(0.1, 1)


def get_detail(ktl: KnowfarTiaoLing):
    try:
        response = request_get(f'http://www.knowfar.net.cn{ktl.title_link}', None)
        print(
            f'请求：{ktl.country}-{ktl.arms}-{ktl.type}-{ktl.subtype}，详情：{ktl.title_link}，状态：{response.status_code}')
        tree = etree.HTML(response.text)
        # 模糊匹配
        # zlly = ''.join(tree.xpath('//*[contains(text(), "职能领域")]/ancestor::p//text()'))
        # 全文本匹配，分类模糊匹配会匹配多个
        # fl = ''.join(tree.xpath('//*[normalize-space()="分类："]/ancestor::p//text()'))

        ktl.title_zh = key_to_value(tree, '期刊名（译）：')
        if not ktl.title_zh:
            ktl.title_zh = translate(ktl.title)
        ktl.internal_number = key_to_value(tree, '内部编号：')
        ktl.country_region = key_to_value(tree, '国家/地区：')
        ktl.functional_areas = key_to_value(tree, '职能领域：')
        functional_areas_sub = key_to_value(tree, '职能领域子分类：')
        if not functional_areas_sub:
            functional_areas_sub = key_to_value_table(tree, '职能领域子分类：')
        ktl.functional_areas_sub = functional_areas_sub

        ktl.service_department = key_to_value(tree, '期刊种类：')
        ktl.classify = key_to_value(tree, '刊类：')
        # ktl.two_classify = key_to_value(tree, '语种：')
        # ktl.responsible_department = key_to_value(tree, '责任部门：')
        ktl.issuing_agency = key_to_value(tree, '出版/主办：')
        ktl.document_language = key_to_value(tree, '语种：')
        ktl.Key_words = key_to_value(tree, '关键词：')
        ktl.word_count = key_to_value(tree, '总期数：')
        ktl.page_count = key_to_value(tree, '创刊日期：')
        ktl.document_size = key_to_value(tree, '期刊简介：')

        ktl.summary_en = ''.join(tree.xpath('//*[@id="text_label_summary_cn"]//text()')).replace('(查看原文)', '')
        # if ktl.summary_en:
        #     ktl.summary_zh = translate(ktl.summary_en, source='en')
        # ktl.file_source_url = ''.join(tree.xpath('//div[@class="item source"]//a/@href'))
    except Exception as e:
        print('采集详情错误\n', str(e))

    all_datas.append(ktl.__dict__)


def key_to_value(tree, key):
    return str_pattern(
        ''.join(tree.xpath(f'//*[normalize-space()="{key}"]/parent::*/following-sibling::node()[@class="c"]//text()'))) \
        .replace(key, '')


def key_to_value_table(tree, key):
    return str_pattern(
        ''.join(tree.xpath(f'//*[normalize-space()="{key}"]/ancestor::table//text()'))) \
        .replace(key, '')


def str_pattern(text: str):
    """
        字符串过滤掉[1]等以及基础网页符等样式
    :param text: 字符串
    :return:
    """
    if not text:
        return ""
    return (re.sub(r'\[\d+]', '', text).strip().replace('&nbsp;', '')
            .replace('\n', '').replace('\t', '').replace('\xa0', '')
            .replace('\r', '').replace('\u3000', '').replace(' ', '')
            .replace(' ', ' ').strip())


def request_get(url, params):
    """
    :param url:
    :param params:
    :return:
    """
    session = requests.Session()
    session.headers = {
        'Cookie': 'cookies_identity=d011c263318c427a96bcfb019aa5d49d; ASP.NET_SessionId=rxn4mqxz51jl0xs5q4bqhyaf; KnowfarData2023_user=id=10017972&userkey=f1a200e8&groupid=1&cookies=c94966673'}
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    response = session.get(
        url=url
    )

    return response


if __name__ == '__main__':
    # 读取文件
    try:
        get_list('美国', '', '', '')
    except Exception as e:
        print(f'采集错误')

    import pandas as pd

    df = pd.DataFrame(all_datas)
    output_path = './美国防务期刊目录2.xlsx'
    df.to_excel(output_path, index=False)
