import os.path
import time
from urllib.parse import quote, urljoin

import requests
import yt_dlp
from DrissionPage import ChromiumPage, ChromiumOptions

# 创建浏览器配置对象，指定浏览器路径
co = ChromiumOptions().set_browser_path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe').set_paths(
    local_port=9111, user_data_path=r'D:\DrissionPage')
# 用该配置创建页面对象
page = ChromiumPage(addr_or_opts=co)
session = requests.Session()
session.impersonate = 'edge101'
session.verify = False
session.headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0'}
session.timeout = 3
sp_dict = {}
# 使用搜索查询来获取并下载发布时间在一年内的视频
tw = {'台湾': {'陆军': ['坦克', '装甲车辆', '火炮', '防空武器', '轻武器', '情报监侦装备'],
               '海军': ['水面舰艇', '潜艇'],
               '空军': ['战斗机', '预警机', '侦察机', '运输机', '直升机', '教练机', '无人机', '导弹装备'],
               '宪兵': [''],
               '海军陆战队': ['']
               },
      }
yn = {'越南': {'陆军': ['坦克', '装甲车辆', '火炮', '防空武器', '战术导弹', '飞机', '无人机'],
               '海军': ['护卫舰', '导弹艇', '近海炮艇/鱼雷艇', '扫雷舰', '潜艇', '两栖舰艇', '飞机'],
               '空军': ['战斗机', '轰炸机', '运输机', '直升机', '教练机'],
               },
      }
hg = {'韩国': {'陆军': ['坦克', '装甲车辆', '火炮', '防空炮'],
               '海军': ['水面舰艇 护卫舰', '水面舰艇 导弹艇', '水面舰艇 驱逐舰', '水面舰艇 补给舰',
                        '水面舰艇 坦克登陆舰', '水面舰艇 两栖攻击舰', '水面舰艇 训练舰', '水面舰艇 布雷舰', '潜艇',
                        '飞机 固定翼飞机', '飞机 直升机', '舰载武器 舰炮', '舰载武器 导弹', '舰载武器 鱼雷',
                        '舰载武器 水雷'],
               '空军': ['战斗机', '空中加油机', '运输机', '空中预警机', '电子侦察机'],
               },
      }
rb = {'日本': {'陆军': ['单兵轻武器', '单兵重火力武器', '车辆载具', '无人武器', '地面装甲', '飞机', '重型武器'],
               '海军': ['水面舰艇', '潜艇', '飞机', '舰载武器'],
               '空军': ['战斗机', '教练机', '运输机', '空中预警机', '侦察机', '运输直升机'],
               },
      }
yd = {'印度': {'陆军': ['坦克', '装甲车辆', '火炮', '防空武器', '导弹', '直升机'],
               '海军': ['航母', '驱逐舰', '护卫舰', '巡逻舰', '导弹艇', '潜艇/核潜艇', '登陆舰', '补给舰', '战斗机'],
               '空军': ['战斗机', '运输机', '预警机', '电子侦察机'],
               },
      }

els = {'俄罗斯': {'陆军': ['坦克', '装甲车辆', '火炮', '防空武器'],
                  '海军': ['辅助作战舰艇', '驱逐舰', '护卫舰', '巡洋舰', '潜艇', '航空母舰'],
                  '空天军': ['战斗机', '运输机', '直升机', '教练机', '轰炸机', 'CAS（近空支援）', '特种任务机', '加油机'],
                  '战略导弹部队': ['空空导弹', '战略导弹', '地空导弹', '反舰导弹', '空地导弹'],
                  '空降兵部队': ['反坦克导弹系统', '轻武器', '战车和装甲运输兵车', '自行反坦克炮', '反无人机装备']
                  },
       }
mg = {'美国': {'陆军': ['坦克', '装甲车辆', '火炮', '防空系统'],
               '海军': ['辅助作战舰艇', '驱逐舰', '护卫舰', '巡洋舰', '潜艇', '航空母舰'],
               '空军': ['战斗机', '运输机', '直升机', '教练机', '轰炸机', 'CAS（近空支援）', '特种任务机', '加油机'],
               '海军陆战队': ['攻击机', '运输直升机', '攻击直升机', '主战坦克', '两栖突击车', '装甲车', '榴弹炮',
                              '两栖攻击舰', '两栖船坞运输舰', '两栖船坞登陆舰', '两栖货运舰'],
               '太空军': ['反坦克导弹系统', '轻武器', '战车和装甲运输兵车', '自行反坦克炮', '反无人机装备'],
               '海岸警卫队': ['舰艇', '船', '飞机']
               },
      }
search_query = "Satellite IoT"
num_results = 1000
download_directory = 'E:\敌方资料\主战装备/'  # 请替换为你想保存视频的目录
# search_and_download_videos(search_query, num_results, download_directory)
from scrapy import Selector

ydl_opts = {
    'quiet': True,
    'extract_flat': True,
    'max_entries': num_results,
    'outtmpl': download_directory + '%(title)s.%(ext)s',
    # 'proxy': 'http://192.168.6.42:10502',
    'cookies': '__ac_nonce=066986ad3008e75147dfb; __ac_signature=_02B4Z6wo00f013UWXjQAAIDCqk2teUgMp3t1NlqAALvp03; csrf_session_id=35bb200a2d19550d60caa9bde7e78e9e; ttwid=1%7CfNsvULSKcb81pOUhnUnu6A4xvRUOOWgGDXs93E2b-kY%7C1721264854%7C5bced8fa485ed8e0dec3e0a3cebb72ebd42f13789689452054388f13d7df6d66; ixigua-a-s=0; UIFID_TEMP=ed7153551a5441a9d274fffa18dd5a4b766749fc0005778d523004468bc84c1faeff76834d954846270611dfe2bab6e3eaaf92b5098256eb2f2f7eff3b54e7e2f7cce374ed5537f854fcdd1c78bb06bf; support_webp=true; support_avif=true; gfkadpd=1768,30523; x-web-secsdk-uid=81ec6db2-d30e-4bec-b95e-8e228c8af888; first_enter_player=%7B%22any_video%22%3A%222.14.0%22%7D; fpk1=U2FsdGVkX1+hTpcxR6DxrVW5J6OG8rtdsTRvQVNhp0PzmBKdeT7ACVAAA8U5r9ICUAyl/JAfXwK5yHenoqZYCA==; fpk2=5f4591689f71924dbd1e95e47aec4ed7; _tea_utm_cache_2285=undefined; UIFID=ed7153551a5441a9d274fffa18dd5a4b766749fc0005778d523004468bc84c1faeff76834d954846270611dfe2bab6e348f5b99c7ebc510a48387dc0d399aa268a7e19d1d7075cd2ec7469176bae672e2353c1f8eca00a1a530d1137f379a3d2e1d10beb4bcbb7fa2059ac491d12e4fc',
    'format': 'mp4',
}


def download_video(url, destination, file):
    response = session.get(url, stream=True)
    response.raise_for_status()
    if not os.path.exists(destination):
        os.mkdir(destination)
    file = file.replace('/', '|')
    with open(f'{destination}{file}', 'wb+') as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)


# with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#     ydl.download(['https://www.ixigua.com/6939755107688907300?fromvsogou=1&wid_try=1'])
def tx(query):
    download_directory = 'E:\敌方资料\主战装备/' + query.replace(' ', '/') + '/'
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'max_entries': num_results,
        'outtmpl': download_directory + '%(title)s.%(ext)s',
        # 'proxy': 'http://192.168.6.42:10502',
        'format': 'mp4',
    }
    url = f'https://v.qq.com/x/search/?q={query}&stag=&smartbox_ab='
    text = session.get(url).text
    page.get(url)
    time.sleep(2)
    text = page.html
    selector = Selector(text=text)
    video_url = [urljoin(url, u) for u in selector.xpath(
        '//div[@class="result_item result_item_h"]/a/@href').getall()]
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(video_url)


def blbl(query):
    download_directory = 'E:\敌方资料\主战装备/' + query.replace(' ', '/') + '/'
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'max_entries': num_results,
        'outtmpl': download_directory + '%(title)s.%(ext)s',
        # 'proxy': 'http://192.168.6.42:10502',
        'format': 'mp4',
    }
    url = f'https://search.bilibili.com/video?keyword={quote(query)}&search_source=5'
    text = session.get(url).text
    selector = Selector(text=text)
    video_url = [urljoin(url, u) for u in selector.xpath(
        '//div[@class="video-list-item col_3 col_xs_1_5 col_md_2 col_xl_1_7 mb_x40"]//div[@class="bili-video-card__wrap __scale-wrap"]/a/@href').getall()]
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(video_url)


def sg(query, pg=1, ydl_opts=None, download_directory='', pages=1, sp_url=None):
    key = query.replace(' ', '_')
    if pg == 1:
        sp_dict[key] = set()
        sp_url = set()
        download_directory = 'E:\敌方资料\主战装备/' + query.replace(' ', '/') + '/'
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'max_entries': num_results,
            'outtmpl': download_directory + '%(title)s.%(ext)s',
            # 'proxy': 'http://192.168.6.42:10502',
            'ignoreerrors': 'only_download',
            'no_warnings': True,
            'format': 'mp4',
        }
    # url = f'https://v.sogou.com/v?ie=utf8&query={quote(query)}'
    url = f'https://v.sogou.com/api/video/shortVideoV2?query={quote(query)}&page={pg}&pagesize=20'
    try:
        text = session.get(url).json()
        # page.get(url)
        # time.sleep(2)
        # text = page.html
        # selector = Selector(text=text)
        # sp = selector.xpath('//li[@class="short-video-item cur"]')
        sp = text.get('data').get('list')
        pages = text.get('data').get('pages', 1)
    except:
        sp = []
        pages = pages
    for s in sp:
        # source = s.xpath('.//*[@class="sort_lst_txt_rgt"]//text()').get()
        source = s.get('site')
        if source not in ['哔哩哔哩', '腾讯视频', '好看视频']:
            continue
        # href = urljoin(url, s.xpath('./a/@href').get())
        href = urljoin(url, s.get('url'))
        page.get(href)
        page.ele('xpath://div[@class="btn"]').click()
        time.sleep(1)
        if source in ['哔哩哔哩', '腾讯视频']:
            sp_url.add(page.url)
        elif source in ['好看视频']:
            try:
                hk_url = page.ele('xpath://video').attr('src')
                hk_title = page.ele('xpath://h1//text()')
                if hk_url:
                    sp_dict[key].update([hk_url])
                    download_video(hk_url, download_directory, f'{hk_title}.{hk_url.split("?")[0].split(".")[-1]}')
            except:
                continue
    if pg >= pages:
        sp_dict[key].update(sp_url)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download(list(sp_url))
        return
    else:
        pg += 1
        return sg(query, pg, ydl_opts, download_directory, pages, sp_url)


def main():
    for k, v in ml.items():
        for kk, vv in v.items():
            for vvv in vv:
                kw = f'{k} {kk} {vvv}'
                print(f'当前:{kw}')
                sg(kw)
                # tx(kw)
                # blbl(kw)
    print(sp_dict)


if __name__ == '__main__':
    main()
