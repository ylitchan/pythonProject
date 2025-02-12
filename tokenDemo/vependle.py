import datetime
import traceback
from io import BytesIO

import pandas as pd
import requests
from apscheduler.schedulers.blocking import BlockingScheduler


def vependle():
    while True:
        try:
            CommunityVote = requests.get('https://api-v2.pendle.finance/bff/v1/ve-pendle/vote-snapshot').json().get(
                'votes')
            data = {i['pool'].get('name'): {'CommunityVote': i.get('percentage')} for i in CommunityVote}
            ProjCommunityVote = requests.get('https://api-v2.pendle.finance/bff/v1/ve-pendle/ongoing-votes').json().get(
                'votes')
            for i in ProjCommunityVote:
                if i['pool'].get('name') in data:
                    data[i['pool'].get('name')].update({'ProjCommunityVote': i.get('percentage')})
            Fees = requests.get('https://api-v2.pendle.finance/bff/v1/ve-pendle/pool-voter-apr-swap-fee').json().get(
                'results')
            for i in Fees:
                if i['pool'].get('name') in data:
                    data[i['pool'].get('name')].update({'VoterAPR': i.get('voterApr'), 'Fees': i.get('swapFee')})
            df = pd.DataFrame.from_dict(data,
                                        orient='index').dropna()  # .reset_index().rename(columns={'index': 'key'})
            df['CommunityVote_rank'] = df['CommunityVote'].rank(ascending=True, method='min')
            df['ProjCommunityVote_rank'] = df['ProjCommunityVote'].rank(ascending=True, method='min')
            df['VoterAPR_rank'] = df['VoterAPR'].rank(ascending=False, method='min')
            df['Fees_rank'] = df['Fees'].rank(ascending=False, method='min')
            df['total'] = (
                    df['CommunityVote_rank'].astype(int) * 0.5 +
                    df['ProjCommunityVote_rank'].astype(int) * 0.5 +
                    df['VoterAPR_rank'].astype(int) +
                    df['Fees_rank'].astype(int)
            )
            df.sort_values(by='total', ascending=True, inplace=True)
            # 将DataFrame转换为CSV内存文件
            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=True)  # utf-8-sig解决中文乱码
            excel_buffer.seek(0)  # 重置指针位置
            files = {
                "media": (
                    f"vependle{datetime.datetime.now().strftime('%Y%m%d')}.xlsx", excel_buffer,
                    "application/octet-stream")
            }
            res = requests.post(
                'https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73&type=file',
                files=files)
            requests.post('https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6f2ec864-c474-4c8f-b069-1e3c35eb7d73',
                          json={
                              "msgtype": "file",
                              "file": {
                                  "media_id": res.json().get('media_id')
                              }
                          })
            break
        except:
            traceback.print_exc()


# 创建BlockingScheduler对象
scheduler = BlockingScheduler()
scheduler.add_job(vependle, 'cron', hour='12', minute='00', second='00', timezone='Asia/Shanghai')
scheduler.start()
