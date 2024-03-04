import json
from tools import *

# member = client_tweet.get_list_members('1639838455760035840').data
# if member:
#     already = [i.id for i in member]
# else:
#     already = []
# consumer = producer.pubsub()
# consumer.subscribe('tg_add')


# def add_member():
#     with requests.session() as session:
#         for m in consumer.listen():
#             user_id = m.get('data')
#             print(user_id)
#             if isinstance(user_id, bytes) and int(
#                     user_id.decode('utf-8')) not in already:  # and client_tweet.get_user(id=user_id):
#                 user_id = int(user_id.decode('utf-8'))
#                 # 發送添加到列表的請求
#                 session.post('https://twitter.com/i/api/graphql/27lfFOrDygiZs382QLttKA/ListAddMember', json={
#                     "variables": {
#                         "listId": "1639838455760035840",
#                         "userId": user_id
#                     },
#                     "features": {
#                         "rweb_lists_timeline_redesign_enabled": False,
#                         "blue_business_profile_image_shape_enabled": True,
#                         "responsive_web_graphql_exclude_directive_enabled": True,
#                         "verified_phone_label_enabled": False,
#                         "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
#                         "responsive_web_graphql_timeline_navigation_enabled": True
#                     },
#                     "queryId": "27lfFOrDygiZs382QLttKA"
#                 }, headers={
#                     'x-csrf-token': 'aa3383f5de290543f2d112d2159d2d69160f153d32f8648852183d816487a844e6023170c0b10bc4bade97f1d2226c0e2ea8239e071aedcdfd2296453fc75b6864b1736c00d28661f3a02de16091e056',
#                     'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
#                     'cookie': 'des_opt_in=Y; g_state={"i_l":4,"i_p":1685978878538}; kdt=Q5t5PoYbZC7V30BrYCwKZzsSt3b612JIMJtmb0pQ; _gcl_au=1.1.2086328013.1685102825; _ga=GA1.2.1852869831.1685180820; _gid=GA1.2.579029748.1685180820; dnt=1; ads_prefs="HBESAAA="; auth_multi="1577862800952930305:864329745d15cc0b8407f8b403bb9c80e88ace79"; auth_token=cf79681343ca5b964ab4fa004c5d9fca2bdce7a9; guest_id=v1:168528420580517298; ct0=aa3383f5de290543f2d112d2159d2d69160f153d32f8648852183d816487a844e6023170c0b10bc4bade97f1d2226c0e2ea8239e071aedcdfd2296453fc75b6864b1736c00d28661f3a02de16091e056; lang=zh-cn; twid=u=1568898000654680064; guest_id_marketing=v1:168528420580517298; guest_id_ads=v1:168528420580517298; personalization_id="v1_M+fBTWkwbZBZWjHzsW7W+w=="',
#                     'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.68'})
#                 # 添加失败重新放入队列
#                 if user_id not in [i.id for i in client_tweet.get_list_members('1639838455760035840').data]:
#                     print(time.strftime('%Y-%m-%d %H:%M:%S %Z %A'), '添加失败,重新放入队列')
#                     producer.publish('tg_add', user_id)
#                     time.sleep(3600)
#                 else:
#                     print(time.strftime('%Y-%m-%d %H:%M:%S %Z %A'), '添加成功,计入已添加')
#                     already.append(user_id)
#                     time.sleep(10)


if __name__ == '__main__':
    Thread(target=add_member, args=[], daemon=True).start()
    while True:
        continue
    # with open('alpha.json', 'r') as f:
    #     for i in json.load(f):
    #         print(i)
    #         q_add.put(int(i))
    # add_member()
