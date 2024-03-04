import requests
from jsonpath_ng import parse
from scrapy import Request
import redis
import scrapy
from ..settings import *


class NewAlphaSpider(scrapy.Spider):
    name = 'newAlpha'
    allowed_domains = ['twitter.com']
    redis_bloom = redis.Redis(host='localhost', port=6379, decode_responses=True)
    session = requests.session()
    alert = []
    id_bloom=set()
    user_dict = {'@doctorDefi2020': 1410877375198285827,
                 '@ugly42061647': 1161902865969025024,
                 '@FedAgentAaron': 1442919050, '@Sajuio8': 1479930165761302531, '@cryptamurai': 914788213763559424,
                 '@vvhader1': 1093579512388804608, '@Luyaoyuan1': 1202404680992575488,
                 '@CryptoGangster6': 1373269670074019841, '@skiesyyyy': 1329534911364042752,
                 '@Henry_VuQuangDu': 1191522172608471040, '@I_am_patrimonio': 1023637918282383361,
                 '@2lambro': 1559193198605774850, '@Makima_sol': 1428066700931571714,
                 '@RASOKA_ETH': 1373674110031515648, '@The_1legendd': 755082450557173760,
                 '@UST_DAO': 1525413531641909249, '@Arron_finance': 1145259912764805120,
                 '@EinsteinYipie': 996220800431669248, '@multichainchad': 1372954317649543171,
                 '@sung_crypto': 1483780590302371848, '@duke_rick1': 1293551150948585474,
                 '@ElCryptoDoc': 1260953582897111042, '@Ekonomeest': 507337880, '@TheRealGapper': 716698266,
                 '@ChadCaff': 1411274211444854785, '@MohammedTunkar4': 946926779226353665,
                 '@thecyptowonk': 703330140844068865, '@LoveKeykey1': 1464985642186674176, '@dawsboss888': 1235634691,
                 '@RaccoonHKG': 1402966572726054915, '@ArbitrumNewsDAO': 1374628085471977478, '@CJCJCJCJ_': 483061902,
                 '@Vikcyter_2': 1497149952421613571, '@Hoangarthur2': 1376714105310965762,
                 '@xiaowuDD666': 1224237649134620673, '@LeNeutron': 1069731982832230400, '@3azima85': 260180304,
                 '@panoskras': 942058868158365696, '@crypto_saint': 873640202329305089,
                 '@snkrseateat': 776808659573538816, '@FractalGiraffe': 1057043659391229957, '@shingboiii': 3398862073,
                 '@SlukaOzella': 1609130699256389632, '@0xdantrades': 984279344, '@lantian560560': 1434104719169888258,
                 '@crypt0_beluga': 1388044400412921856, '@defi_antcrypto': 1594223633605459968,
                 '@BiliSquare': 887928113312677889, '@Ed_x0101': 1359150440663949319,
                 '@cryptomemez': 1300868746412789761, '@dao_ust': 1568898000654680064, '@lawrenx_': 1038021937304416256,
                 '@crypt0detweiler': 1389581148146356230, '@0xYelf': 1452979796145840140,
                 '@Juliooofive': 926593414086447104, '@monosarin': 1392695766934822912,
                 '@criptopaul': 870778296950247426, '@EricCryptoman': 826381583489855490,
                 '@sululukz99': 1465355451412131841, '@0xsn0wball': 873095548756045825, '@DoloNFT': 1404971067672875015,
                 '@MiddleChildPabk': 885225812986699776, '@CryptoKaduna': 1103404363861684236,
                 '@ApeOClock': 1401346770458669057, '@ilovegains': 749749112, '@Sherv1n_eth': 1476504086178676742,
                 '@berdXspade': 1459514982891024387, '@yuyue_chris': 1490949502261665792,
                 '@RomAin11515879': 1379376517671751681, '@yakuza_crypto': 1329171696155193345}
    degen_dict = {
        "862333798138003456": "degenlinxi",
        "4920186276": "Ren_leilei",
        "1293551150948585474": "duke_rick1",
        "1254538550906728448": "MrCartographer_",
        "159227459": "0xminion",
        "939580637219975168": "Crypt00_Pepe",
        "1397450323963252739": "wassiecapital",
        "1235634691": "dawsboss888",
        "3084205185": "0xLordAlpha",
        "929827324563947521": "fomosaurus",
        "873095548756045825": "0xsn0wball",
        "1450289232317009921": "KK827827",
        "1147903249380335616": "0xMonkeyboy",
        "1434061045958692864": "0xdragon8848",
        "1390144583946969093": "cchungccc",
        "943285914008043520": "Uncle_DeFi",
        "1358984475388956673": "Morty0x",
        "1414758107985715202": "0xjz_ ",
        "1426013345514065922": "0xLeDude",
        "1448559817375641602": "FINT1121",
        "784068635958644736": "cryptodetweiler",
        "1202404680992575488": "Luyaoyuan1",
        "823535150231273472": "antoniayly",
        "1266776489363509249": "ACryptoApe",
        "1376848871079481349": "HONKA_YO",
        "332086054": "TianranZhang",
        "1299696400259833857": "shuishui21",
        "942058868158365696": "panoskras",
        "1525803620838412294": "0xYami",
        "1452979796145840140": "0xYelf"
    }

    def start_requests(self):
        for l, n in self.degen_dict.items():
            yield Request(
                'https://twitter.com/i/api/graphql/sKlU5dd_nanz9P2CxBt2sg/Following?variables=%7B%22userId%22%3A%22{}%22%2C%22count%22%3A20%2C%22includePromotedContent%22%3Afalse%7D&features=%7B%22rweb_lists_timeline_redesign_enabled%22%3Atrue%2C%22responsive_web_graphql_exclude_directive_enabled%22%3Atrue%2C%22verified_phone_label_enabled%22%3Afalse%2C%22creator_subscriptions_tweet_preview_api_enabled%22%3Atrue%2C%22responsive_web_graphql_timeline_navigation_enabled%22%3Atrue%2C%22responsive_web_graphql_skip_user_profile_image_extensions_enabled%22%3Afalse%2C%22tweetypie_unmention_optimization_enabled%22%3Atrue%2C%22responsive_web_edit_tweet_api_enabled%22%3Atrue%2C%22graphql_is_translatable_rweb_tweet_is_translatable_enabled%22%3Atrue%2C%22view_counts_everywhere_api_enabled%22%3Atrue%2C%22longform_notetweets_consumption_enabled%22%3Atrue%2C%22responsive_web_twitter_article_tweet_consumption_enabled%22%3Afalse%2C%22tweet_awards_web_tipping_enabled%22%3Afalse%2C%22freedom_of_speech_not_reach_fetch_enabled%22%3Atrue%2C%22standardized_nudges_misinfo%22%3Atrue%2C%22tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled%22%3Atrue%2C%22longform_notetweets_rich_text_read_enabled%22%3Atrue%2C%22longform_notetweets_inline_media_enabled%22%3Atrue%2C%22responsive_web_media_download_video_enabled%22%3Afalse%2C%22responsive_web_enhance_cards_enabled%22%3Afalse%7D&fieldToggles=%7B%22withArticleRichContentState%22%3Afalse%7D'.format(
                    l), dont_filter=True, callback=self.parse, headers=LIST_LIST[0][2],
                meta={'username': n, 'headers_account': LIST_LIST[0][0], 'headers': LIST_LIST[0][2]})

    def parse(self, response, **kwargs):
        # print(response.status, response.meta.get('username'), time.strftime('%Y-%m-%d %H:%M:%S %Z %A'))
        if response.status == 200:
            degen = response.meta.get('username')
            following = parse('$..user_results.result').find(response.json())
            # print(parse('$..screen_name').find(following[0].value)[0].value)
            for u in following:
                rest_id = parse('$..rest_id').find(u.value)
                expanded_url = parse('$..expanded_url').find(u.value)
                # 佈隆過濾器去掉之前爬過的推文
                if bool(rest_id and expanded_url) and self.redis_bloom.zadd(degen, {rest_id[0].value: 1}):
                    self.redis_bloom.zincrby('degen_all', 1, rest_id[0].value)
                    expanded_url = expanded_url[0].value
                    new_follow = {'username': parse('$..screen_name').find(u.value)[0].value,
                                  'restID': parse('$..rest_id').find(u.value)[0].value,
                                  'bio': parse('$..description').find(u.value)[0].value,
                                  'profileImageUrl': parse('$..profile_image_url_https').find(u.value)[0].value,
                                  'createdAt': parse('$..created_at').find(u.value)[0].value,
                                  'followersCount': parse('$..followers_count').find(u.value)[0].value,
                                  'listedCount': parse('$..listed_count').find(u.value)[0].value,
                                  'expanded_url': expanded_url}
                    print('当前新增关注', new_follow)
                    if new_follow['restID'] not in self.id_bloom:
                        self.id_bloom.add(new_follow['restID'])
                        self.alert.append(new_follow)
