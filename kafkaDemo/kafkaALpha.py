import datetime
import random
import time

import openai
import requests
from kafka import KafkaProducer, KafkaConsumer

def add_member(userId):
    headers = {
        'cookie': 'des_opt_in=Y; _gcl_au=1.1.116267149.1676257589; g_state={"i_l":4,"i_p":1681369247236}; _ga_BYKEBDM7DS=GS1.1.1679899771.1.1.1679899844.0.0.0; _gid=GA1.2.1222660834.1680783998; at_check=true; mbox=PC#5d50de66cc054e10bf959bf00d0b670c.38_0#1744731433|session#db24585874f049b1b132445cb93bebc8#1681488493; _ga=GA1.2.1915858432.1679573193; kdt=2RNumTWyrbgn13h0nBHx95uYSPlUa6qMK390ud8K; _ga_34PHSZMC42=GS1.1.1681533194.15.0.1681533194.0.0.0; dnt=1; auth_multi="1568898000654680064:17e8044520b62a806dc73e68c70a019d1918e70f"; auth_token=614cb847793f6b268a64e8cf6ea05479d38bb67d; guest_id_ads=v1:168153922613435906; guest_id_marketing=v1:168153922613435906; lang=en; guest_id=v1:168153922613435906; twid=u=1573326306661793792; ct0=5bb87294748eabc856cd95ffc52dad00c7ef7abe56a299feebef81091739e80961b2842233a9a2222093250ad0270f0aedcb49afaeded4e26fa13092ad22b2cda67ba9a6ddc4ef96c139e351f9cbcaaa; personalization_id="v1_A5Cjem2NxpnAPzInu7PDFA=="',
        'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.39',
        'x-csrf-token': '5bb87294748eabc856cd95ffc52dad00c7ef7abe56a299feebef81091739e80961b2842233a9a2222093250ad0270f0aedcb49afaeded4e26fa13092ad22b2cda67ba9a6ddc4ef96c139e351f9cbcaaa'
        }
    var = {
        "variables": {
            "listId": "1646881802609655808",
            "userId": userId
        },
        "features": {
            "blue_business_profile_image_shape_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True
        },
        "queryId": "x0smnIS1jLLXToRYg70g4Q"
    }
    res = requests.post('https://twitter.com/i/api/graphql/x0smnIS1jLLXToRYg70g4Q/ListAddMember', headers=headers,
                      json=var)
    print(res)
# # 创建生产者实例
# producer = KafkaProducer(bootstrap_servers=['localhost:9092'])
#
# # 发送消息
# producer.send('test', b'Hello, Kafka!')

# 创建消费者实例
consumer_add = KafkaConsumer('test', bootstrap_servers=['localhost:9092'], group_id='test-group')
consumer_alpha = KafkaConsumer('alpha', bootstrap_servers=['localhost:9092'], group_id='alpha-group')
# 消费消息
for message in consumer_add:
    print(message.value.decode('utf-8'),datetime.datetime.now())
    add_member(message.value.decode('utf-8'))
    time.sleep(random.uniform(300, 3600))


