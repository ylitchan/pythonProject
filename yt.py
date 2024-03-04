import re
import subprocess
from dateutil.parser import parse
import requests
import yt_dlp
from datetime import datetime, timedelta


def search_and_download_videos(query, max_results=10, download_path='downloads/'):
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'max_entries': max_results,
        'outtmpl': download_path + '%(title)s.%(ext)s',
        'proxy':'http://192.168.6.42:10502',
        'format':'mp4',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        if 'entries' in result:
            for video in result['entries']:
                try:
                    if re.search('Satellite.*?IoT', video['title'], re.I) and video['url'].startswith('https://www.youtube.com/watch'):
                        video_date = parse(re.search('dateText.*?}',requests.get(video['url'],proxies={'https':'http://192.168.6.42:10502'}).text).group().split('"')[-2])
                        one_year_ago = datetime.now() - timedelta(days=365)
                        if not video_date >= one_year_ago:
                            print(f"下载视频: {video['title']}")
                            try:
                                ydl.download([video['url']])
                            except:
                                continue
                except:
                    continue


# 使用搜索查询来获取并下载发布时间在一年内的视频
search_query = "Satellite IoT"
num_results = 300
download_directory = 'yt_downloads/'  # 请替换为你想保存视频的目录
search_and_download_videos(search_query, num_results, download_directory)
