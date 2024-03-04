import json
import os
import time
import requests
import tweepy
from confluent_kafka import Producer, Consumer
import queue

q = queue.Queue()
with open('alpha.json', 'r') as f:
    q.put(json.load(f))
client = tweepy.Client(os.environ.get("tweetapi"))
# already = []


already = [i.id for i in client.get_list_members('1644339127071162369').data]
# already =[]

def add_list_member():
    with requests.session() as session:
        while True:
            users = q.get(block=True)
            for user_id in users:
                print(user_id)
                if int(user_id) not in already:
                    already.append(int(user_id))
                    print(user_id, '加入列表', already)
                    session.post('https://twitter.com/i/api/graphql/Vupsa0nLEL7N6gmmQhnJlA/ListAddMember', json={
                        "variables": {
                            "listId": "1644339127071162369",
                            "userId": user_id
                        },
                        "features": {
                            "rweb_lists_timeline_redesign_enabled": False,
                            "blue_business_profile_image_shape_enabled": True,
                            "responsive_web_graphql_exclude_directive_enabled": True,
                            "verified_phone_label_enabled": False,
                            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                            "responsive_web_graphql_timeline_navigation_enabled": True
                        },
                        "queryId": "Vupsa0nLEL7N6gmmQhnJlA"
                    }, headers={
                        'x-csrf-token': '6339238b203be60c9b0ab8ba4cc98cd7d1f31e02d88c3478eeece89e83b343471369cf904260defa9a2237dc0c1860713959d4cee2c2a10796959e1550691ef568c7e8ac0cf144623e6790dfd0c4070d',
                        'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
                        'cookie': 'des_opt_in=Y; _gcl_au=1.1.116267149.1676257589; _ga_BYKEBDM7DS=GS1.1.1679899771.1.1.1679899844.0.0.0; _gid=GA1.2.1757760020.1683559675; guest_id=v1:168363730335520730; _twitter_sess=BAh7CSIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%0ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCGUuowCIAToMY3NyZl9p%0AZCIlZDAxMmJiMDI5YmNhOTJiOTIxNjQ0OTIxNjAyMTEzMjY6B2lkIiVmM2Rh%0AYmRiMjY1Y2EyMmZmZDE5YmI5MmYyYmIzZGFkMQ%3D%3D--ab1802ef47a8ff7e6cda1ca423546a564422414b; kdt=FVr1ummSIpgb0IwyW6DoM3211uqKQmKnRvd3zEMX; auth_token=b73eb4a5421a798e55a1017db7f6d042ad69614c; ct0=6339238b203be60c9b0ab8ba4cc98cd7d1f31e02d88c3478eeece89e83b343471369cf904260defa9a2237dc0c1860713959d4cee2c2a10796959e1550691ef568c7e8ac0cf144623e6790dfd0c4070d; twid=u=1577862800952930305; att=1-RpbShyTitZPSuYaFG41Edzs6x4W9Yamq9S4kavt9; guest_id_marketing=v1:168363730335520730; guest_id_ads=v1:168363730335520730; at_check=true; lang=en; mbox=PC#5d50de66cc054e10bf959bf00d0b670c.38_0#1746882789|session#622950c8337748b0abe0c5c55579d18e#1683639849; _ga_34PHSZMC42=GS1.1.1683637987.18.1.1683637990.0.0.0; _ga=GA1.2.1915858432.1679573193; personalization_id="v1_xipf0V2oaGf9Ff0BcZaQhg=="',
                        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.68'})
                    time.sleep(10)


add_list_member()
