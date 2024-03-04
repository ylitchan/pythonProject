import datetime
import json
from utils.tools import *

# 创建消费者实例
# consumer = KafkaConsumer('alpha', bootstrap_servers=['localhost:9092'], group_id='alpha-group')
ISHTAR = KafkaConsumer('ISHTAR', bootstrap_servers=['localhost:9092'], group_id='ISHTAR-group', api_version=(0, 10, 2))
ISHTARcher = KafkaConsumer('ISHTARcher', bootstrap_servers=['localhost:9092'], group_id='ISHTARcher-group',
                           api_version=(0, 10, 2))
ISHTARcher.subscribe('ISHTARcher')
for i in ISHTAR:
    print(i)


# admin_client = KafkaAdminClient(
#     bootstrap_servers="localhost:9092",
#     client_id="admin"
# )

# 获取所有topic列表
# topics = admin_client.list_topics()

# 循环删除每个topic
# for topic in topics:
#     print(topic)
# admin_client.delete_topics([topic])
# 消费消息
def ishtarcher():
    hf_list = ['我会模拟fate中的ISHTAR']
    for message in ISHTARcher:
        data = json.loads(message.value.decode('utf-8'))
        msg = parse('$..text').find(data)[0].value
        print('当前kafka消费时间', datetime.datetime.now(), hf_list, msg)
        thread_ts = parse('$..thread_ts').find(data)
        if thread_ts:
            if thread_ts[0].value == '1682605196.796199':
                ISHTAR_tg.send_message(5865410419, msg)
            continue
        channel = parse('$..channel').find(data)[0].value
        bot_id = parse('$..bot_id').find(data)
        if channel == 'D054NGFG2TY' and not bot_id:
            hf = chat_gpt([{"role": "assistant", "content": hf_list[0]}, {"role": "user", "content": msg}])
            requests.post('https://hooks.slack.com/services/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',
                          json={'text': hf}, timeout=10)
            hf_list[0] = hf


def ishtar():
    for message in ISHTAR:
        try:
            with open('input.oga', 'wb') as f:
                f.write(message.value)
            audioclip = mpe.AudioFileClip("input.oga")
            audioclip.write_audiofile("output.wav")
            r = sr.Recognizer()
            with sr.AudioFile('output.wav') as source:
                # 将语音文件读取为AudioData对象
                audio_data = r.record(source)
            # 使用Google Speech Recognition进行识别
            text = r.recognize_google(audio_data, language='zh-CN')
        except:
            text = message.value.decode('utf-8')
        finally:
            # 输出识别结果
            print('当前kafka消费时间', datetime.datetime.now(), text)
            ISHTAR_slack.chat_postMessage(channel=CHANNEL_ID, text="<@U053SG7AC01> " + text, as_user=True,
                                          thread_ts='1682605196.796199')

# ISHTARcher_thread = threading.Thread(target=ishtarcher)
# ISHTARcher_thread.start()
# ISHTAR_thread = threading.Thread(target=ishtar)
# ISHTAR_thread.start()
