import os
import requests
import telebot
from jsonpath_ng import parse

for i, j in {'2': 3}.items():
    print(i, j)
ISHTARider_tg = telebot.TeleBot(os.environ.get("ISHTARider_tg"))
ISHTARider_tg.send_message(-980470620, 'msg')
while True:
    try:
        a = requests.get(
            'https://twitter.com/i/api/graphql/2vTVUCjWcooreYYLCK0nLQ/Following?variables=%7B%22userId%22%3A%221479930165761302531%22%2C%22count%22%3A20%2C%22includePromotedContent%22%3Afalse%7D&features=%7B%22rweb_lists_timeline_redesign_enabled%22%3Atrue%2C%22responsive_web_graphql_exclude_directive_enabled%22%3Atrue%2C%22verified_phone_label_enabled%22%3Afalse%2C%22creator_subscriptions_tweet_preview_api_enabled%22%3Atrue%2C%22responsive_web_graphql_timeline_navigation_enabled%22%3Atrue%2C%22responsive_web_graphql_skip_user_profile_image_extensions_enabled%22%3Afalse%2C%22tweetypie_unmention_optimization_enabled%22%3Atrue%2C%22responsive_web_edit_tweet_api_enabled%22%3Atrue%2C%22graphql_is_translatable_rweb_tweet_is_translatable_enabled%22%3Atrue%2C%22view_counts_everywhere_api_enabled%22%3Atrue%2C%22longform_notetweets_consumption_enabled%22%3Atrue%2C%22responsive_web_twitter_article_tweet_consumption_enabled%22%3Afalse%2C%22tweet_awards_web_tipping_enabled%22%3Afalse%2C%22freedom_of_speech_not_reach_fetch_enabled%22%3Atrue%2C%22standardized_nudges_misinfo%22%3Atrue%2C%22tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled%22%3Atrue%2C%22longform_notetweets_rich_text_read_enabled%22%3Atrue%2C%22longform_notetweets_inline_media_enabled%22%3Atrue%2C%22responsive_web_media_download_video_enabled%22%3Afalse%2C%22responsive_web_enhance_cards_enabled%22%3Afalse%7D&fieldToggles=%7B%22withArticleRichContentState%22%3Afalse%7D',
            headers={
                'cookie': 'des_opt_in=Y; _gcl_au=1.1.2086328013.1685102825; g_state={"i_l":4,"i_p":1688478693716}; mbox=PC#dcbf0b6907a44fc787c69c2e7fbb6db1.38_0#1749817959|session#dfcb512ba2904d55935a82566010ca90#1686575019; _ga_34PHSZMC42=GS1.1.1686573165.8.1.1686573197.0.0.0; _ga=GA1.2.1852869831.1685180820; _gid=GA1.2.294164188.1687613031; guest_id=v1%3A168786544727770809; _twitter_sess=BAh7CSIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCJfbrPyIAToMY3NyZl9p%250AZCIlZDg3NjgwMjFhMzM2NTlkMDk5ODBhNWRlODkxZmMxZTE6B2lkIiUzODQ1%250AZTdlMjU2YmVjMjg4NzA5ZDkyMDkzMjhmNGE2NQ%253D%253D--a94cd0d85c0de17912c602cbc2735a48c330706d; kdt=4ehLccAOsysCnhFL4xjoTAWFtCBt3kZUybHadSVA; auth_token=7065bebbd829f7a19bc859c45abf93e9037f058f; ct0=6f3f8e9ea306c4af97e2df3b8ebdb7cd25162ef6497ab9ae9d48d99665c3facf06cbb8ebb9cbbce534dbc4dd1029cca01d5e7e5b7d248b6ba5d1d3e78159526cf116b9a8efa3709d546dd127f759b98b; lang=en; twid=u%3D1577862800952930305; guest_id_marketing=v1%3A168786544727770809; guest_id_ads=v1%3A168786544727770809; external_referer=padhuUp37zj0pruP7hlZooEqjdY0o%2FwTJRt%2BCNvMedk%3D|0|8e8t2xd8A2w%3D; personalization_id="v1_4HI6BGDyopJqayLoZudUxQ=="',
                'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
                'X-Csrf-Token': '6f3f8e9ea306c4af97e2df3b8ebdb7cd25162ef6497ab9ae9d48d99665c3facf06cbb8ebb9cbbce534dbc4dd1029cca01d5e7e5b7d248b6ba5d1d3e78159526cf116b9a8efa3709d546dd127f759b98b',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.68'})
        # print(666666666, a.text)
        print(type(a.content))
        users = parse('$..entryId').find(a.json())
        print(len(users))
        ISHTARider_tg.send_message(-1001982993052, a.text)
        break
    except:
        print(555555)
        continue
