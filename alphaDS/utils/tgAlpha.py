from threading import Thread
from tools import *


def process_item(data):
    item = LaunchItem()
    item['tweet_alpha'] = data[0]
    item['tweet_text'] = data[1]
    item['tweet_time'] = parser.parse(data[2])
    item['tweet_id'] = data[3]
    item['tweet_user'] = data[4]
    item['user_thumb'] = 'blob:https://web.tel.onl/07ca81cf-6388-4ceb-bb1c-83535f4a7a7f'
    print('生成item')
    key = list({i.lower() for i in re.findall(
        r'\blaunch|sale\b|\blive|\blist|发射|\bcontract|\baddress|\bido|\bairdrop|\bmint|\bavailable',
        item['tweet_text'], re.I)})
    if key:
        print('处理带信息的tg消息')
        tweet_text = item['tweet_text']
        msg = [{"role": "assistant",
                "content": "代币时间:%Y-%m-%d %H:%M:%S %Z %A,代币token名称:$token,代币chain名称:#chain,代币contract地址:0x"},
               {"role": "user", "content": tweet_text + "\n根据今天的当前时间today's now:" + time.strftime(
                   '%Y-%m-%d %H:%M:%S %Z %A') + '推测并按照之前回复的格式提取以上内容中代币token名称(格式为$token)/代币chain名称(格式为#chain)/代币contract地址(格式为0x)/' + '时间(格式为%Y-%m-%d %H:%M:%S %Z %A)/'.join(
                   ['代币' + k for k in key] + [''])}]
        print('gpt正在分析文本', key)
        hf = parse('$..hf').find(chat_gpt(msg))[0].value
        print('GPT返回结果', hf)
        # print(len(re.findall(r'unknown', hf, re.I)))
        alpha = re.findall(
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \w+ \w+|\$[A-Za-z0-9_]+|#[A-Za-z0-9_]+|0x[A-Za-z0-9_]+',
            hf, re.I)
        alpha_time = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \w+ \w+', str(alpha), re.I)
        if alpha_time:
            item['tweet_gpt'] = hf
            item['alpha_time'] = ' \| '.join(alpha + key)
            msg = '[' + item['tweet_user'] + ']' + '(https://web\.tel\.onl/\#' + data[6] + ')' + ' @[' + item[
                'tweet_alpha'] + ']' + '(https://web\.tel\.onl/\#@' + data[5] + ')  \|  [' + item[
                      'alpha_time'] + ']' + '(https://t\.me/' + \
                  data[5] + '/' + item['tweet_id'] + ')\n\n' + '`' + item[
                      'tweet_text'] + '`'
            msg = msg.replace('_', r'\_').replace('-', r'\-').replace('#', r'\#')
            ISHTARider_tg.send_message(-980470620, msg
                                       , parse_mode="MarkdownV2", disable_web_page_preview=False)
            item['alpha_datetime'] = parser.parse(alpha_time.group())
            item.save()
    print('处理完毕', item, sep='\n')


while True:
    data = q_alpha.get(block=True)
    Thread(target=process_item, args=[data]).start()
