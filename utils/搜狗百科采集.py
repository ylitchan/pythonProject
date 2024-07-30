# @Date: 2024/6/12
# @Author: ylitchan
# @Source: rdti_crawl_defense
# @Site:
import io
import logging
import mimetypes
import os.path
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from urllib.parse import quote
from urllib.parse import urljoin

from DrissionPage import ChromiumPage, ChromiumOptions
# import cairosvg
from PIL import Image
from curl_cffi import requests
from langchain.callbacks.manager import CallbackManagerForRetrieverRun
from langchain.schema import Document, BaseRetriever
from lxml import etree

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(funcName)s %(lineno)d %(levelname)s: %(message)s')

PROXIES = {}
# 创建浏览器配置对象，指定浏览器路径
co = ChromiumOptions().set_browser_path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe').set_paths(
    local_port=9111, user_data_path=r'D:\DrissionPage')
# 用该配置创建页面对象
page = ChromiumPage(addr_or_opts=co)
page.get(
    'https://www.sogou.com/sogou?ie=utf8&insite=baike.sogou.com&query=%E5%8D%95%E5%85%B5%E8%A3%85%E5%A4%87')
time.sleep(3)


class NetRetrieval(BaseRetriever):
    tags: List[str] = ['联网检索']
    type: str = 'other'
    session = ''
    """
    联网检索器
    """

    @staticmethod
    def get_str(node, xpath):
        return ''.join(node.xpath(xpath)).replace(' ', '').replace('\n', '')

    def connect_session(self):
        """图谱连接"""
        session = requests.Session()
        session.impersonate = 'chrome110'
        session.proxies = PROXIES
        session.verify = False
        session.timeout = 1
        session.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36', }

        cookie_json = {
            "SUID": "2B65C3866555A00A0000000064A63582",
            "SUV": "1688614249755118",
            "ssuid": "997402876",
            "browerV": "3",
            "osV": "1",
            "sw_uuid": "486035100",
            "sg_uuid": "2098833454",
            "_qimei_uuid42": "18710141930100b8b4f29971582177b2c6f9d74ec6",
            "_qimei_fingerprint": "66c056ef43307198b16dd7127a90c7df",
            "_qimei_q36": "",
            "_qimei_h38": "e1476accb4f29971582177b202000002e18710",
            "SGINPUT_UPSCREEN": "1721132811249",
            "ABTEST": "3|1721985906|v17",
            "IPLOC": "CN3502",
            "PHPSESSID": "549b1v77u0boq0ocppkk9c5q67",
            "SNUID": "691AE5657E78605D5E2A5BBE7F7FE0AB",
            "sst0": "498",
            "LSTMV": "769%2C30",
            "LCLKINT": "13248493"
        }
        cookies = page.cookies(as_dict=True, all_domains=False)
        if cookies:
            cookie_json.update(
                {k: v for k, v in cookies.items() if k in cookie_json.keys()})
        # try:
        #     res = session.get(f'https://www.sogou.com/web?ie=utf8&query=666')
        #     if res.cookies.jar:
        #         cookie_json.update(
        #             {cookie.name: cookie.value for cookie in res.cookies.jar if cookie.name in cookie_json.keys()})
        #     if res.request.headers.get('Cookie'):
        #         cookie_json.update(
        #             {key: value for key, value in
        #              dict([l.split("=", 1) for l in res.request.headers['Cookie'].split('; ')]).items() if
        #              key in cookie_json.keys()})
        #     session.headers.update({'Cookie': '; '.join([f"{k}={v}" for k, v in cookie_json.items()])})
        # except:
        #     logging.info('cookies获取失败')
        self.session = session

    def get_content(self, url, context_xpath=''):
        """
        获取网页正文，使用gne自动抽取
        :param url:
        :param headers:
        :param proxies:
        :param context_xpath:
        :return:
        """
        st = time.time()
        content = ''
        images_list = []
        try:
            if 'https://weixin.sogou.com' in url:
                content_res = self.session.get(url.replace(' ', '%20'))
                url = ''.join(re.findall(r"\+=.*?'(.*?)'", content_res.text)).replace(' ', '%20')
                content_res = self.session.get(url)
                # logging.info(f"获取 {url} 响应: {time.time() - st}")
            elif 'www.sogou.com' in url:
                content_res = self.session.get(url)
                url = re.findall("URL='(.*?)'", content_res.text)[0]
                # content_res = self.session.get(url)
                page.get(url)
                time.sleep(5)
                content_res = page.html
            else:
                content_res = requests.get(url, proxies=PROXIES, impersonate='chrome110', verify=False)
            return content_res, [], url
            html = self._get_html_from_response(content_res)
            extractor = GeneralNewsExtractor()
            result = extractor.extract(html, body_xpath=context_xpath)
            content = re.sub(
                '\n+|( \n)+|消息来源:|((http|https)://)?(www\.)?([a-zA-Z0-9_\-]+(\.[a-zA-Z]{2,})+)(/[a-zA-Z0-9_\-.,@?^=%&:/~+#]*)?',
                '', result.get('content'))
            images_list = result.get('images') + etree.HTML(html).xpath('//body//img//@data-src')
            if images_list:
                images_list = [urljoin(url, il) for il in images_list if il]
        except Exception as e:
            logging.info(f"获取 {url} 错误: {e}")
        logging.info(f"获取 {url} 解析: {time.time() - st}")
        return content, images_list, url

    def sogou_keyword(self, keyword: str):
        results = []
        try:
            # 列表文章 //div[@tpl="se_com_default"]
            # 列表文章来源 //div[@tpl="se_com_default"]//span[@class="c-color-gray"]
            response = self.session.get(
                f'''https://www.sogou.com/web?ie=utf8&query={quote(keyword)}''')
            if '此验证码用于确认这些请求是您的正常行为而不是自动程序发出的，需要您协助验证。' in response.text:
                logging.info('反爬认证，ip封锁')
                return []
            tree = etree.HTML(response.text)
            lists = tree.xpath('//ul[@class="news-list"]/li | //div[@class="vrwrap"]')[:10]
            thread_pool = ThreadPoolExecutor(max_workers=10)
            # self.get_baidu_info(lists[1])
            futures = [thread_pool.submit(self.get_sogou_info, lt, response.url) for lt in lists]
            # 使用as_completed方法来获取已完成的任务
            for future in as_completed(futures):
                result_info = future.result()
                if result_info:
                    results.append(result_info)
            thread_pool.shutdown()
            # for lt in lists:
            #     result_info = self.get_sogou_info(lt)
            #     if result_info:
            #         results.append(result_info)
        except Exception as e:
            logging.info(f"搜狗采集错误: {e}")
        return results

    def sogou_wechat(self, keyword: str):
        results = []
        for p in range(1):
            self.connect_session()
            p += 1
            try:
                # 列表文章 //div[@tpl="se_com_default"]
                # 列表文章来源 //div[@tpl="se_com_default"]//span[@class="c-color-gray"]
                response = self.session.get(
                    f'''https://www.sogou.com/sogou?query={quote(keyword.split("_")[-1])}&ie=utf8&insite=baike.sogou.com''')
                # if '此验证码用于确认这些请求是您的正常行为而不是自动程序发出的，需要您协助验证。' in response.text:
                #     logging.info('搜狗微信反爬认证，ip封锁')
                # response = self.session.get(
                #     f'''https://www.sogou.com/web?ie=utf8&query={quote(keyword)}''')
                if '此验证码用于确认这些请求是您的正常行为而不是自动程序发出的，需要您协助验证。' in response.text:
                    logging.info(f'{p}页：搜狗网页反爬认证，ip封锁')
                    sys.exit()
                tree = etree.HTML(response.text)
                lists = tree.xpath(f'//div[@class="special-wrap title-newblue border-radius baike200107"]//a[.//h3]')
                thread_pool = ThreadPoolExecutor(max_workers=10)
                # self.get_baidu_info(lists[1])
                futures = [thread_pool.submit(self.get_sogou_info, lt, response.url, keyword) for lt in lists[:1]]
                # 使用as_completed方法来获取已完成的任务
                for future in as_completed(futures):
                    result_info = future.result()
                    if result_info:
                        results.append(result_info.metadata['articleAddress'])
                thread_pool.shutdown()
                # for lt in lists:
                #     result_info = self.get_sogou_info(lt)
                #     if result_info:
                #         results.append(result_info)
            except Exception as e:
                logging.info(f"搜狗采集错误: {e}")
                return
            finally:
                time.sleep(10)
        return results

    def get_all_but_last(self, input_string: str, delimiter='_'):
        """
        通过切割字符串，获取除最后一个字符串的字符串
        :param input_string:
        :param delimiter:
        :return:
        """
        parts = input_string.split(delimiter)
        if len(parts) > 1:
            return '/'.join(parts[:-1])
        return input_string

    def get_img(self, tree, directory, d):
        tree = tree.xpath('//div[@class="lemma_container"]')[0]
        try:
            for e in tree.xpath(
                    '//div[@class="lemma_toolbar"] | //div[@class="lemma_focus_wrap"] | //*[@class="btn_edit"]'):
                e.getparent().remove(e)
            img_tags = tree.xpath('//img')
        except:
            raise Exception('图片获取错误')
        # 修改所有img标签的src属性
        for img_tag in img_tags:
            for j in img_tag.attrib.values():
                if j.startswith('http'):
                    try:
                        res = self.session.get(j.split(' ')[0])
                        res.raise_for_status()
                        media_type = mimetypes.guess_type('a.' + res.url.split('?')[0].split('.')[-1].split('/')[0])[0]
                        media_ext = mimetypes.guess_extension(media_type)
                        img_byte = res.content
                        if 'svg' in media_ext:
                            # 使用 cairosvg 将 SVG 转换为 PNG 格式的字节流
                            img_format = 'svg'
                        else:
                            img_byte = res.content
                            img_io = io.BytesIO(img_byte)
                            img = Image.open(img_io)
                            img.verify()
                            # 获取图像格式
                            img_format = img.format.lower()
                        # 生成保存路径
                        # 生成一个随机UUID
                        random_uuid = uuid.uuid1()
                        img_path = f'{random_uuid}.{img_format}'
                        directory_new = f"{directory}/img"
                        abs_fold = os.path.join(r'D:/pythonProject/utils/', directory_new.replace('./', ''))
                        if not os.path.exists(abs_fold):
                            os.makedirs(abs_fold)
                        save_path = os.path.join(f"{directory_new}", img_path)
                        if 'svg' in media_ext:
                            with open(save_path, 'wb') as imgf:
                                imgf.write(img_byte)
                        else:
                            # 保存图像到本地
                            Image.open(io.BytesIO(img_byte)).save(save_path)
                        img_tag.set('src', quote(f'./img/{img_path}'))
                        break
                    except:
                        continue
        # # 将修改后的HTML内容写回文件
        # ele = tree.xpath('//div[@class="lemma_container"]')[0]
        # 将修改后的HTML内容写回文件
        modified_html = etree.tostring(tree, pretty_print=True, method="html", encoding='unicode')
        with open(f'{directory}/{d.metadata["title"]}.html', 'w', encoding='utf-8') as f:
            f.write(modified_html)

    def get_sogou_info(self, lt, url, q=''):
        """
        获取百度搜索引擎信息
        :param lt:
        :param headers:
        :return:
        """
        d = Document(page_content='')
        d.metadata['title'] = ''.join(
            lt.xpath('.//h3//text()')).strip()
        d.metadata['articleAddress'] = urljoin(url, ''.join(
            lt.xpath('.//@href')[0]))
        d.metadata['summary'] = '''self.get_str(lt, './/p[@class="txt-info"]//text()')'''
        d.metadata['source'] = '''self.get_str(lt,
                                            '(.//div[@class="s-p"] | .//*[@class="citeurl "] |.//*[@id="sogou_vr_30010462_source_0"])[1]//text()').split(
            '-')[0].strip()'''
        d.metadata['accountHead'] = ''
        d.metadata[
            'imgAddress'] = '''{'sub': [urljoin(d.metadata['articleAddress'], i) for i in lt.xpath('.//img//@src')]}'''
        # 百度百家号、百度知道有cookie反爬
        not_sites = ['baijiahao', 'zhidao.baidu.com']
        if d.metadata['articleAddress'] and not any(item in d.metadata['articleAddress'] for item in not_sites):
            content = self.get_content(url=d.metadata['articleAddress'])
            if content[0]:
                # 使用lxml解析HTML内容
                parser = etree.HTMLParser()
                tree = etree.fromstring(content[0], parser)
                folder = self.get_all_but_last(q)
                folder = f'./zzzb/{folder}'
                abs_fold = os.path.join(r'D:/pythonProject/utils/', folder.replace('./', ''))
                if not os.path.exists(abs_fold):
                    os.makedirs(abs_fold)
                self.get_img(tree, folder, d)
                # d.page_content = content[0]
                # d.metadata['imgAddress']['sub'].extend(content[1])
                d.metadata['articleAddress'] = content[-1]
                return d

    @staticmethod
    def _get_html_from_response(response):
        """
        格式化响应html
        :param response:
        :return:
        """
        if response.encoding != 'ISO-8859-1':
            # return response as a unicode string
            html = response.text
        else:
            html = response.content
            if 'charset' not in response.headers.get('content-type'):
                charset_re = re.compile(r'<meta.*?charset=["\']*(.+?)["\'>]', flags=re.I)
                pragma_re = re.compile(r'<meta.*?content=["\']*;?charset=(.+?)["\'>]', flags=re.I)
                xml_re = re.compile(r'^<\?xml.*?encoding=["\']*(.+?)["\'>]')
                encodings = (
                        charset_re.findall(response.text)
                        + pragma_re.findall(response.text)
                        + xml_re.findall(response.text)
                )
                if len(encodings) > 0:
                    response.encoding = encodings[0]
                    html = response.text
        return html or ''

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun):
        self.connect_session()
        query = query.strip()  # + ' darpa科研项目' if self.type != 'other' else query.strip()
        relevant_docs = []
        thread_pool = ThreadPoolExecutor(max_workers=100)
        st = time.time()
        futures = [thread_pool.submit(self.sogou_wechat, query)]
        # 使用as_completed方法来获取已完成的任务
        for future in as_completed(futures):
            result_info = future.result()
            if result_info:
                relevant_docs.extend(result_info)
        thread_pool.shutdown()
        return relevant_docs
        # logging.info(time.time() - st)


if __name__ == '__main__':
    ret = NetRetrieval(type='project')
    with open('D:\pythonProject\新文件 5.txt', 'r', encoding='utf-8') as f:
        kw = f.readlines()
    for ii, kk in enumerate(kw):
        # while True:
        #     question = input("请输入问题：")
        if ii < 368:
            continue
        logging.info(f'第{ii}:{kk}')
        result = ret.invoke(kk)
        logging.info(f'完成{result}')
        time.sleep(10)
        # logging.info(result)
