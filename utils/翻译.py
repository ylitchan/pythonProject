"""
@Project :   wspider
@File    :   google_tran.py
@Time    :   2024/1/18 11:32
@Author  :   lwxie
@Desc    :
"""

from typing import Union, List

from pygtrans import Translate, Null

# PROXY = 'http://192.168.8.42:10502'
PROXY = 'http://127.0.0.1:7890'
PROXIES = {
    "http": PROXY,
    "https": PROXY
}
PROXIES = {}


def translate(text: Union[str, List[str]], target: str = 'zh-CN', source: str = 'auto'):
    """
    谷歌文本翻译，支持批量翻译
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
        if isinstance(content, list):
            # 批量
            res_tests = [c.translatedText for c in content]
            return res_tests
        return content.translatedText
    except Exception as e:
        print(f"google tran error: {e}")
        return ""


def translate_long(text: Union[str, List[str]], target: str = 'zh-CN', source: str = 'auto'):
    """
    谷歌文本翻译，支持按需分段翻译
    :param text: 待翻译文本或文本列表
    :param target: 翻译目标语言
    :param source: 源语言
    :return: 翻译后的单个文本或文本列表（如果输入是列表）
    """
    try:
        if not text:
            return text

        client = Translate(target=target, source=source, proxies=PROXIES)
        max_chunk_size = 500000  # 每段最大长度为 500,000 字符

        if isinstance(text, str):
            text = [text]
            return_list = False
        else:
            return_list = True

        results = []

        for t in text:
            if len(t) > max_chunk_size:
                # 如果文本超过最大长度，分段翻译
                num_chunks = (len(t) + max_chunk_size - 1) // max_chunk_size
                chunks = [t[i * max_chunk_size:(i + 1) * max_chunk_size] for i in range(num_chunks)]
                translated_chunks = []

                for chunk in chunks:
                    translated = client.translate(chunk)
                    if isinstance(translated, Null):
                        # 翻译失败时返回原始段落
                        translated_chunks.append(chunk)
                    else:
                        translated_chunks.append(translated.translatedText)

                results.append(''.join(translated_chunks))
            else:
                # 直接翻译单个文本段落
                translated = client.translate(t)
                if isinstance(translated, Null):
                    results.append(t)  # 翻译失败时返回原始文本
                else:
                    results.append(translated.translatedText)

        if not return_list:
            return results[0]  # 如果输入是单个字符串，返回单个翻译结果
        else:
            return results  # 如果输入是字符串列表，返回翻译结果列表

    except Exception as e:
        print(f"谷歌翻译出错：{e}")
        return ''


if __name__ == '__main__':
    to_en_list = translate(['测试', '翻译'], target='en')
    to_en = translate('准将', target='en')
    print(to_en_list)
    print(to_en)
