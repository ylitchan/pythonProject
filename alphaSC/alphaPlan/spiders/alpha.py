import datetime
import random
import time

from ..items import TweetlItem
import scrapy
from scrapy import Request

class AlphaSpider(scrapy.Spider):
    name = 'alpha'

    allowed_domains = ['twitter.com']
    start_urls =['https://twitter.com/i/api/graphql/-_Z4thx55wBFXl3AYBW_1g/ListLatestTweetsTimeline?variables=%7B%22listId%22%3A%22{}%22%2C%22count%22%3A1%2C%22withDownvotePerspective%22%3Afalse%2C%22withReactionsMetadata%22%3Afalse%2C%22withReactionsPerspective%22%3Afalse%7D&features=%7B%22responsive_web_twitter_blue_verified_badge_is_enabled%22%3Atrue%2C%22responsive_web_graphql_exclude_directive_enabled%22%3Atrue%2C%22verified_phone_label_enabled%22%3Afalse%2C%22responsive_web_graphql_timeline_navigation_enabled%22%3Atrue%2C%22responsive_web_graphql_skip_user_profile_image_extensions_enabled%22%3Afalse%2C%22tweetypie_unmention_optimization_enabled%22%3Atrue%2C%22vibe_api_enabled%22%3Atrue%2C%22responsive_web_edit_tweet_api_enabled%22%3Atrue%2C%22graphql_is_translatable_rweb_tweet_is_translatable_enabled%22%3Atrue%2C%22view_counts_everywhere_api_enabled%22%3Atrue%2C%22longform_notetweets_consumption_enabled%22%3Atrue%2C%22tweet_awards_web_tipping_enabled%22%3Afalse%2C%22freedom_of_speech_not_reach_fetch_enabled%22%3Afalse%2C%22standardized_nudges_misinfo%22%3Atrue%2C%22tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled%22%3Afalse%2C%22interactive_text_enabled%22%3Atrue%2C%22responsive_web_text_conversations_enabled%22%3Afalse%2C%22longform_notetweets_richtext_consumption_enabled%22%3Afalse%2C%22responsive_web_enhance_cards_enabled%22%3Afalse%7D'.format(i) for i in ['1567732782700367875','1622670732416229393','1620704962530643973','1639838455760035840','1639614947109015553','1641366241532338176']]
    cookies=[{'des_opt_in': 'Y', '_gcl_au': '1.1.116267149.1676257589', 'g_state': '{"i_l":4,"i_p":1681369247236}', '_ga_BYKEBDM7DS': 'GS1.1.1679899771.1.1.1679899844.0.0.0', 'mbox': 'PC#5d50de66cc054e10bf959bf00d0b670c.38_0#1743478298|session#588b81b0c51c476c89ecc2e190b96e91#1680235358', '_ga_34PHSZMC42': 'GS1.1.1680233475.10.1.1680233505.0.0.0', '_ga': 'GA1.2.1915858432.1679573193', '_gid': 'GA1.2.1222660834.1680783998', 'gt': '1644906262113697792', 'kdt': 'Z3OdCWN6PkJiRhCcUfHEA4O2zWq3ZJ2MIgFn1fSg', 'ads_prefs': '"HBERAAA="', 'auth_multi': '"1568898000654680064:ddc86a06fadbca76319f2484ce8ead062f440835"', 'auth_token': 'cf9bb31eb63b8e3e05e8369d287de00f36259694', 'guest_id_ads': 'v1:168101800908229947', 'guest_id_marketing': 'v1:168101800908229947', 'lang': 'en', 'guest_id': 'v1:168101800908229947', 'twid': 'u=1577862800952930305', 'ct0': '5d54053bb46518b6eae62429e3ac8a7d76fd9bbbf4de72d7de25f6286ce9f6aabb063b15343c4b941b21d4a77d62d75764b061b8e49f285db120b02db6f7c878ea2ba385c682518a58e38d5fe760fbc9', 'personalization_id': '"v1_9MAr+iey/BOWvItd/ATJtA=="'}]
    headers=[{'authorization':'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA','x-twitter-auth-type':'OAuth2Session','x-csrf-token':'5d54053bb46518b6eae62429e3ac8a7d76fd9bbbf4de72d7de25f6286ce9f6aabb063b15343c4b941b21d4a77d62d75764b061b8e49f285db120b02db6f7c878ea2ba385c682518a58e38d5fe760fbc9','user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.62'}]
    def start_requests(self):
        for url in self.start_urls:
            yield Request(url, dont_filter=True,callback=self.parse,cookies=self.cookies[0],headers=self.headers[0])



    def parse(self, response):
        print(response.status,datetime.datetime.now())

        if response.status == 200:
            only=response.json()['data']['list']['tweets_timeline']['timeline']['instructions'][0]['entries'][0]
            theone = only['content']['itemContent']['tweet_results']['result']
            item = TweetlItem()
            item['tweet_id']=only['sortIndex']
            item['tweet_user'] = theone['core']['user_results']['result']['legacy']['screen_name']
            item['tweet_text']=theone['legacy']['full_text']+theone.get('quoted_status_result',{}).get('result',{}).get('legacy',{}).get('full_text','')+theone['legacy'].get('retweeted_status_result',{}).get('result',{}).get('legacy',{}).get('full_text','')+theone['legacy'].get('retweeted_status_result',{}).get('result',{}).get('quoted_status_result',{}).get('result',{}).get('legacy',{}).get('full_text','')
            if theone['legacy']['entities'].get('media',[{}])[0].get('media_url_https',''):
                item['tweet_media']=theone['legacy']['entities'].get('media',[{}])[0].get('media_url_https','')
            elif theone.get('quoted_status_result',{}).get('result',{}).get('legacy',{}).get('entities',{}).get('media',[{}])[0].get('media_url_https',''):
                item['tweet_media']=theone.get('quoted_status_result', {}).get('result', {}).get('legacy', {}).get('entities', {}).get(
                    'media', [{}])[0].get('media_url_https', '')
            elif theone['legacy'].get('retweeted_status_result',{}).get('result',{}).get('legacy',{}).get('entities',{}).get('media',[{}])[0].get('media_url_https',''):
                item['tweet_media']=theone['legacy'].get('retweeted_status_result', {}).get('result', {}).get('legacy', {}).get('entities',
                                                                                                            {}).get(
                    'media', [{}])[0].get('media_url_https', '')
            elif theone['legacy'].get('retweeted_status_result',{}).get('result',{}).get('quoted_status_result',{}).get('result',{}).get('legacy',{}).get('entities',{}).get('media',[{}])[0].get('media_url_https',''):
                item['tweet_media']=theone['legacy'].get('retweeted_status_result', {}).get('result', {}).get('quoted_status_result',
                                                                                          {}).get('result', {}).get(
                    'legacy', {}).get('entities', {}).get('media', [{}])[0].get('media_url_https', '')
            else:
                item['tweet_media'] =''
            print(item)
            yield item
        else:
            time.sleep(60)
        index=random.randint(0,0)
        cookies=self.cookies[index]
        headers=self.headers[index]
        print(index)
        yield Request(url=response.url,callback=self.parse,cookies=cookies,headers=headers,dont_filter=True)
