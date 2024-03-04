import datetime
import schedule
from utils.tools import *


#
# alpha = LaunchInfo.objects.filter(tweet_tag__icontains=time.strftime('%Y-%m-%d')).values('tweet_alpha',
#                                                                                          'tweet_tag',
#                                                                                          'tweet_user', 'tweet_id',
#                                                                                          'tweet_text')
#
# index = 0
# while index < len(alpha):
#     msg = '\n\n'.join([time.strftime('%Y-%m-%d'), "🚀Today's Alpha"] + [
#         '[' + i['tweet_user'] + ']' + '(https://twitter\.com/' + i['tweet_user'] + ')' + ' @[' + i[
#             'tweet_alpha'] + ']' + '(https://twitter\.com/' + i['tweet_alpha'] + ')  \|  [' + i[
#             'tweet_tag'] + ']' + '(https://twitter\.com/' + i['tweet_user'] + '/status/' + i['tweet_id'] + ')'
#         for i in
#         alpha[index:index + 9]]).replace('_', r'\_').replace('-', r'\-').replace('#', r'\#')
#     ISHTARider_tg.send_message(-1001982993052, msg, parse_mode="MarkdownV2", disable_web_page_preview=False)
#     index += 9


def do_task():
    print(datetime.datetime.now())
    # 这里是要执行的事务
    alpha = LaunchInfo.objects.filter(tweet_tag__icontains=time.strftime('%Y-%m-%d')).values('tweet_alpha',
                                                                                             'tweet_tag',
                                                                                             'tweet_user', 'tweet_id',
                                                                                             'tweet_text', 'list_account')
    index = 0
    while index < len(alpha):
        msg = '\n\n'.join([time.strftime('%Y-%m-%d'), "🚀Today's Alpha"] + [
            '[' + i['tweet_user'] + ']' + '(https://twitter\.com/' + i['tweet_user'] + ')' + ' @[' + i[
                'tweet_alpha'] + ']' + '(https://twitter\.com/' + i['tweet_alpha'] + ')  \|  [' + i[
                'tweet_tag'] + ']' + '(https://twitter\.com/' + i['tweet_user'] + '/status/' + i[
                'tweet_id'] + ')  \|  ' + i['list_account']
            for i in
            alpha[index:index + 9]]).replace('_', r'\_').replace('-', r'\-').replace('#', r'\#')
        ISHTARider_tg.send_message(-1001982993052, msg, parse_mode="MarkdownV2", disable_web_page_preview=False)
        index += 9


# 设置每天的 8 点执行任务
# do_task()
schedule.every().day.at("08:30").do(do_task)

while True:
    schedule.run_pending()
    time.sleep(60)
