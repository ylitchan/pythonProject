import random
import re
from jsonpath_ng import parse
import time
from scrapy import Request
from pybloom_live import ScalableBloomFilter
from dateutil import parser
from alphaPlan.settings import ACCOUNT_LIST, LIST_LIST
from ..items import *


class AlphaSpider(scrapy.Spider):
    name = 'alpha'
    allowed_domains = ['twitter.com']
    sbfilter = ScalableBloomFilter(mode=ScalableBloomFilter.SMALL_SET_GROWTH)
    last_time = time.time()

    def start_requests(self):
        for i in LIST_LIST:
            # index = random.randint(0, len(ACCOUNT_LIST) - 1)
            yield Request(
                'https://twitter.com/i/api/graphql/-_Z4thx55wBFXl3AYBW_1g/ListLatestTweetsTimeline?variables=%7B%22listId%22%3A%22{}%22%2C%22count%22%3A1%2C%22withDownvotePerspective%22%3Afalse%2C%22withReactionsMetadata%22%3Afalse%2C%22withReactionsPerspective%22%3Afalse%7D&features=%7B%22responsive_web_twitter_blue_verified_badge_is_enabled%22%3Atrue%2C%22responsive_web_graphql_exclude_directive_enabled%22%3Atrue%2C%22verified_phone_label_enabled%22%3Afalse%2C%22responsive_web_graphql_timeline_navigation_enabled%22%3Atrue%2C%22responsive_web_graphql_skip_user_profile_image_extensions_enabled%22%3Afalse%2C%22tweetypie_unmention_optimization_enabled%22%3Atrue%2C%22vibe_api_enabled%22%3Atrue%2C%22responsive_web_edit_tweet_api_enabled%22%3Atrue%2C%22graphql_is_translatable_rweb_tweet_is_translatable_enabled%22%3Atrue%2C%22view_counts_everywhere_api_enabled%22%3Atrue%2C%22longform_notetweets_consumption_enabled%22%3Atrue%2C%22tweet_awards_web_tipping_enabled%22%3Afalse%2C%22freedom_of_speech_not_reach_fetch_enabled%22%3Afalse%2C%22standardized_nudges_misinfo%22%3Atrue%2C%22tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled%22%3Afalse%2C%22interactive_text_enabled%22%3Atrue%2C%22responsive_web_text_conversations_enabled%22%3Afalse%2C%22longform_notetweets_richtext_consumption_enabled%22%3Afalse%2C%22responsive_web_enhance_cards_enabled%22%3Afalse%7D'.format(
                    i[1]), dont_filter=True, callback=self.parse, headers=ACCOUNT_LIST[0][2],
                meta={'list_account': i[0], 'headers_account': ACCOUNT_LIST[0][0],'headers':ACCOUNT_LIST[0][2], 'index': 0})

    def parse(self, response, **kwargs):
        print(response.status, response.meta.get('list_account'), time.strftime('%Y-%m-%d %H:%M:%S %Z %A'))
        if response.status == 200:
            only = parse('$..entries[0]').find(response.json())[0].value
            tweet_id = parse('$..entryId').find(only)[-1].value
            tweet_id = re.findall(r'\d+', tweet_id)[-1]
            tweet_text = parse('$..full_text').find(only)
            # 佈隆過濾器去掉之前爬過的推文
            if '1644920028696031235' in response.url and len(tweet_text) == 1:
                item = CallerItem()
                item['tweet_text'] = tweet_text[-1].value
            elif '1644920028696031235' not in response.url:
                item = LaunchItem()
                item['tweet_text'] = '\n'.join([i.value for i in tweet_text])
            else:
                item = None
            if not self.sbfilter.add(tweet_id + item.__class__.__name__) and item:
                item['list_account'] = response.meta.get('list_account')
                item['tweet_id'] = tweet_id
                all_user = parse('$..screen_name').find(only)[0:2]
                item['tweet_user'] = all_user[0].value
                item['tweet_alpha'] = all_user[-1].value
                item['tweet_time'] = parser.parse(parse('$..created_at').find(only)[-1].value)
                all_thumb = parse('$..profile_image_url_https').find(only)
                item['user_thumb'] = all_thumb[0].value
                item['alpha_thumb'] = all_thumb[-1].value
                tweet_media = parse('$..media_url_https').find(only)
                item['tweet_media'] = tweet_media[0].value if tweet_media else ''
                print('未处理' + item.__class__.__name__, item, sep='\n')
                yield item
        else:
            time.sleep(600)
        time.sleep(300)
        # 隨機headers
        index = response.meta.get('index') + 1
        if index == len(ACCOUNT_LIST):
            index = 0
        headers = ACCOUNT_LIST[index][2]
        print('请求头账号', ACCOUNT_LIST[index][0])
        response.meta['headers_account'] = ACCOUNT_LIST[index][0]
        response.meta['headers'] = headers
        response.meta['index'] = index
        yield Request(url=response.url, callback=self.parse, headers=headers, dont_filter=True,
                      meta=response.meta)
