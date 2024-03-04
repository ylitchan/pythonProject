# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
import pytesseract
from PIL import Image
from threading import Thread


# useful for handling different item types with a single interface
class AlphaplanPipeline:
    # def process_item(self, item, spider):
    #     return item
    def close_spider(self, spider):
        msg_tg = [
            f"✨️{i.get('username')}[https://twitter.com/{i.get('username')}]:{int(spider.redis_bloom.zscore('degen_all', i.get('restID')))}/{len(spider.degen_dict)}"
            # f"{i.get('username')}の详情:\n✨️{int(spider.redis_bloom.zscore('degen_all', i.get('restID')))}/{len(spider.degen_dict)}\nhttps://twitter.com/{i.get('username')}\nbio:{i.get('bio')}\nexpandedUrl:{i.get('expanded_url')}\nfollowersCount:{i.get('followersCount')}\nlistedCount:{i.get('listedCount')}")
            for i in spider.alert if
            spider.redis_bloom.zscore('degen_all', i.get('restID')) / len(spider.degen_dict) >= 0.15]
        print(msg_tg)
        if msg_tg:
            spider.session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=2caca472-4893-490d-aa1b-76e69f4e9b3c',
                headers={'Content-Type': 'application/json'}, json={
                    "msgtype": "text",
                    "text": {'content': '\=\=今日新增\=\=\n\n' + '\n'.join([i for i in msg_tg])}
                })


class TweetPipeline(object):
    def __init__(self):
        super().__init__()

    def process_item(self, item, spider):
        # 判斷是否有圖片需要ocr
        if item['tweet_media']:
            res = session.get(item['tweet_media'], stream=True)
            with open('alpha.png', 'wb') as file:
                # 每128个流遍历一次
                for data in res.iter_content(128):
                    # 把流写入到文件，这个文件最后写入完成就是，selenium.png
                    file.write(data)  # data相当于一块一块数据写入到我们的图片文件中
            media_text = pytesseract.image_to_string(Image.open('alpha.png'), lang='chi_sim+eng')
        else:
            media_text = ''
        tweet_text = item['tweet_text'] + '\n' + media_text
        # 將鏈接去除掉,再去發給ai
        tweet_text = re.sub(r'https?://[^\s]+', '', tweet_text)
        # key過濾無用推文
        if isinstance(item, LaunchItem):
            key = list({i.lower() for i in re.findall(
                r'\blaunch|sale\b|\blive|\blist|发射|\bcontract|\baddress|\bido|\bairdrop|\bmint|\bca\b|\bavailable|\bgiv.*?away\b|https://t.co/[A-Za-z0-9]+',
                tweet_text, re.I)})
            # if key:
            #     print('处理带信息的发射推文')
            #     # if item['tweet_media']:
            #     #     res = requests.get(item['tweet_media'], stream=True)
            #     #     with open('alpha.png', 'wb') as file:
            #     #         # 每128个流遍历一次
            #     #         for data in res.iter_content(128):
            #     #             # 把流写入到文件，这个文件最后写入完成就是，selenium.png
            #     #             file.write(data)  # data相当于一块一块数据写入到我们的图片文件中
            #     #     media_text = pytesseract.image_to_string(Image.open('alpha.png'), lang='chi_sim+eng')
            #     # else:
            #     #     media_text = ''
            #     # tweet_text = item['tweet_text'] + '\n' + media_text
            #     msg = [{"role": "assistant",
            #             "content": "代币时间:%Y-%m-%d %H:%M:%S %Z %A,代币token名称:$token,代币chain名称:#chain,代币contract地址:0x"},
            #            {"role": "user", "content": tweet_text + "\n根据今天的当前时间today's now:" + time.strftime(
            #                '%Y-%m-%d %H:%M:%S %Z %A') + '推测并按照之前回复的格式提取以上内容中代币token名称(格式为$token)/代币chain名称(格式为#chain)/代币contract地址(格式为0x)/' + '时间(格式为%Y-%m-%d %H:%M:%S %Z %A)/'.join(
            #                ['代币' + k for k in key] + [''])}]
            #     print('gpt正在分析文本', key)
            #     hf = parse('$..hf').find(chat_gpt(msg))[0].value
            #     print('GPT返回结果', hf)
            #     item['tweet_gpt'] = hf
            #     # print(len(re.findall(r'unknown', hf, re.I)))
            #     alpha = re.findall(
            #         r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \w+ \w+|\$[A-Za-z0-9_]+|#[A-Za-z0-9_]+|0x[A-Za-z0-9_]+',
            #         hf, re.I)
            #     alpha_time = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \w+ \w+', str(alpha), re.I)
            #     item['alpha_time'] = ' \| '.join(alpha + key)
        else:
            key = re.search(r'\$\w+', tweet_text, re.I)
        if key:
            Thread(target=process_item, args=[key, tweet_text, item]).start()
            #     if alpha_time:
            #         item['tweet_gpt'] = hf
            #         item['alpha_time'] = ' \| '.join(alpha + key)
            #         item['alpha_datetime'] = parser.parse(alpha_time.group())
            #         msg = '[' + item['tweet_user'] + ']' + '(https://twitter\.com/' + item[
            #             'tweet_user'] + ')' + ' @[' + item[
            #                   'tweet_alpha'] + ']' + '(https://twitter\.com/' + item[
            #                   'tweet_alpha'] + ')  \|  [' + item['alpha_time'] + ']' + '(https://twitter\.com/' + \
            #               item['tweet_user'] + '/status/' + item['tweet_id'] + ')\n\n' + '`' + item[
            #                   'tweet_text'] + '`'
            #         msg = msg.replace('_', r'\_').replace('-', r'\-').replace('#', r'\#')
            #         ISHTARider_tg.send_message(-980470620, msg
            #                                    , parse_mode="MarkdownV2", disable_web_page_preview=False)
            #         item['alpha_datetime'] = parser.parse(alpha_time.group())
            #         item.save()
            # print('LaunchItem处理完毕', item, sep='\n')
            # print(tweet_text, hf, sep='\n') 发送消息 producer.send('alpha', str('@' + item['tweet_user'] + '\n' + hf +
            # '\n详见以下推文https://twitter.com/' + item[ 'tweet_user'] + '/status/' + item['tweet_id'] + '\n' + item[
            # 'tweet_text']).encode('utf-8'))
        #     print('处理CallerlItem')
        #     ISHTAR_slack.chat_postMessage(channel=CHANNEL_ID,
        #                                   text="<@U053SG7AC01> " + '@' + item['tweet_id'] + ':\n' + tweet_text,
        #                                   as_user=True,
        #                                   thread_ts='1684411853.122829')
        #     consumer = producer.pubsub()
        #     consumer.subscribe(item['tweet_id'])
        #     for m in consumer.listen():
        #         try:
        #             hf = m.get('data').decode('utf-8')
        #             print('获取到claude回复', hf)
        #             alpha_time = re.findall('\$[A-Za-z0-9_]+', hf, re.I)
        #             if alpha_time:
        #                 item['alpha_time'] = ' \| '.join(alpha_time)
        #                 item['tweet_gpt'] = hf
        #                 item['alpha_datetime'] = item['tweet_time']
        #             #     item.save()
        #             break
        #         except:
        #             continue
        # if item['alpha_time']:
        #     msg = '[' + item['tweet_user'] + ']' + '(https://twitter\.com/' + item[
        #         'tweet_user'] + ')' + ' @[' + item[
        #               'tweet_alpha'] + ']' + '(https://twitter\.com/' + item[
        #               'tweet_alpha'] + ')  \|  [' + item['alpha_time'] + ']' + '(https://twitter\.com/' + \
        #           item['tweet_user'] + '/status/' + item['tweet_id'] + ')\n' + item['alpha_datetime'].strftime(
        #         '%Y-%m-%d %H:%M:%S %Z %A') + '\n\n`' + item[
        #               'tweet_text'] + '`'
        #     msg = msg.replace('_', r'\_').replace('-', r'\-').replace('#', r'\#')
        #     ISHTARider_tg.send_message(-980470620, msg
        #                                , parse_mode="MarkdownV2", disable_web_page_preview=False)
        #     item['alpha_datetime'] = parser.parse(alpha_time.group())
        #     item.save()
        # print('处理完毕', item, sep='\n')
        return item
