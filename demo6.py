import requests
from jsonpath_ng import parse

session = requests.Session()
dic = {}
account_list = [('dao_ust', '1639838455760035840', {
    'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
    'Cookie': 'des_opt_in=Y; _gcl_au=1.1.2086328013.1685102825; g_state={"i_l":4,"i_p":1688478693716}; mbox=PC#dcbf0b6907a44fc787c69c2e7fbb6db1.38_0#1749817959|session#dfcb512ba2904d55935a82566010ca90#1686575019; _ga_34PHSZMC42=GS1.1.1686573165.8.1.1686573197.0.0.0; _ga=GA1.2.1852869831.1685180820; kdt=YY5epcm5ePgzHpX3oXabVshhh27g18lEHMuYH7v4; _gid=GA1.2.1842052750.1687350267; dnt=1; auth_multi="1577862800952930305:1bedb7ef5487e0ca4faa75e233f94abf2b7e59eb|1573326306661793792:b8da11bc85168214fe4b0b6957cc318478a3a6e2"; auth_token=5503c671b8069c470766fdea2d66ba5fb9a86538; guest_id=v1%3A168735332699056847; ct0=e19897d7753735caf08114c7dddf607957a28df444b776c21a2b74b16100bd05790d7cdf5b6c32478aa17ed0eb87520b121e6c39235f656d71973706e3c270b64f7c888caee8ebd78b5d003f9ab97ae8; lang=zh-cn; twid=u%3D1568898000654680064; guest_id_marketing=v1%3A168735332699056847; guest_id_ads=v1%3A168735332699056847; personalization_id="v1_quUYBDnAEMLTiqebrNCQJQ=="',
    'X-Csrf-Token': 'e19897d7753735caf08114c7dddf607957a28df444b776c21a2b74b16100bd05790d7cdf5b6c32478aa17ed0eb87520b121e6c39235f656d71973706e3c270b64f7c888caee8ebd78b5d003f9ab97ae8'}),
                ('dao_ust2', '1667054883219083264', {
                    'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
                    'Cookie': 'des_opt_in=Y; _gcl_au=1.1.2086328013.1685102825; g_state={"i_l":4,"i_p":1688478693716}; mbox=PC#dcbf0b6907a44fc787c69c2e7fbb6db1.38_0#1749817959|session#dfcb512ba2904d55935a82566010ca90#1686575019; _ga_34PHSZMC42=GS1.1.1686573165.8.1.1686573197.0.0.0; _ga=GA1.2.1852869831.1685180820; _gid=GA1.2.294164188.1687613031; gt=1672929356564557831; kdt=NM3A3BOWMx37GmPm0Z4Lhye1iVVcztVSlceYK2X6; lang=zh-cn; dnt=1; auth_multi="1121014957422907392:fb739a04e9f024dfa6860b837b9c437aaa93f0fa"; auth_token=450444b721eb21cfa581e4195ac7384545dd89cc; guest_id=v1%3A168769252221011498; ct0=1a3a1a3f3f3497d56d958b4363e1514dbfd5f90dd3cec4455a20d0223c656bfd9786b307c96508e2f85501c6c137ae9dab5cddf5f6b3655c6d3b11f72d39041376df5f2b01920c2b148c3389e8fc1bca; twid=u%3D1666748651618865153; guest_id_marketing=v1%3A168769252221011498; guest_id_ads=v1%3A168769252221011498; personalization_id="v1_BLq9lVhxG6JsQL5ss6yM5g=="',
                    'X-Csrf-Token': '1a3a1a3f3f3497d56d958b4363e1514dbfd5f90dd3cec4455a20d0223c656bfd9786b307c96508e2f85501c6c137ae9dab5cddf5f6b3655c6d3b11f72d39041376df5f2b01920c2b148c3389e8fc1bca'}),
                ('dao_ust3', '1646838020363153408', {
                    'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
                    'Cookie': 'des_opt_in=Y; _gcl_au=1.1.2086328013.1685102825; g_state={"i_l":4,"i_p":1688478693716}; mbox=PC#dcbf0b6907a44fc787c69c2e7fbb6db1.38_0#1749817959|session#dfcb512ba2904d55935a82566010ca90#1686575019; _ga_34PHSZMC42=GS1.1.1686573165.8.1.1686573197.0.0.0; _ga=GA1.2.1852869831.1685180820; kdt=YY5epcm5ePgzHpX3oXabVshhh27g18lEHMuYH7v4; _gid=GA1.2.1842052750.1687350267; dnt=1; lang=zh-cn; auth_multi="1568898000654680064:5503c671b8069c470766fdea2d66ba5fb9a86538|1577862800952930305:1bedb7ef5487e0ca4faa75e233f94abf2b7e59eb|1573326306661793792:b8da11bc85168214fe4b0b6957cc318478a3a6e2"; auth_token=bc4e0b0e13059d5f73217d2e512963ab84d2b03c; guest_id=v1%3A168735792361821059; ct0=5f9cd12434705cc3270ebe333b8b3cfa6f4df1fbd15306751b4c853d4cfb650082da2b70ebecb3d60552549c151c4fa4d17a8ef20969692024ec5aeabc572bfc2e7a2634167d48c2347572bf87a20c54; twid=u%3D1121014957422907392; guest_id_marketing=v1%3A168735792361821059; guest_id_ads=v1%3A168735792361821059; personalization_id="v1_dhsI3gVYY2Bo9x07dcPgzg=="',
                    'X-Csrf-Token': '5f9cd12434705cc3270ebe333b8b3cfa6f4df1fbd15306751b4c853d4cfb650082da2b70ebecb3d60552549c151c4fa4d17a8ef20969692024ec5aeabc572bfc2e7a2634167d48c2347572bf87a20c54'})]
for i in {'@0xdantrades', '@0xsn0wball', '@0xYelf', '@2lambro', '@3azima85', '@ApeOClock', '@ArbitrumNewsDAO',
          '@Arron_finance', '@berdXspade', '@BiliSquare', '@ChadCaff', '@CJCJCJCJ_', '@criptopaul',
          '@crypt0_beluga', '@crypt0detweiler', '@cryptamurai', '@crypto_saint', '@CryptoGangster6',
          '@CryptoK63140864', '@CryptoKaduna', '@cryptomemez', '@dao_ust', '@dawsboss888', '@defi_antcrypto',
          '@doctorDefi2020', '@DoloNFT', '@duke_rick1', '@Ed_x0101', '@EinsteinYipie', '@Ekonomeest',
          '@ElCryptoDoc', '@EricCryptoman','@FedAgentAaron', '@FractalGiraffe', '@Henry_VuQuangDu',
          '@Hoangarthur2', '@I_am_patrimonio', '@ilovegains', '@ISHTARider', '@Juliooofive', '@lantian560560',
          '@lawrenx_', '@LeNeutron', '@LoveKeykey1', '@Luyaoyuan1', '@Makima_sol', '@MiddleChildPabk',
          '@MohammedTunkar4', '@monosarin', '@multichainchad', '@panoskras', '@RaccoonHKG', '@RASOKA_ETH',
          '@RomAin11515879', '@Sajuio8', '@Sherv1n_eth', '@shingboiii', '@skiesyyyy', '@SlukaOzella',
          '@snkrseateat', '@sululukz99', '@sung_crypto', '@The_1legendd', '@thecyptowonk', '@TheRealGapper',
          '@ugly42061647', '@UST_DAO', '@Vikcyter_2', '@vvhader1', '@xiaowuDD666', '@yakuza_crypto',
          '@yuyue_chris'}:
    new_user = session.get(
        'https://twitter.com/i/api/graphql/qRednkZG-rn1P6b48NINmQ/UserByScreenName?variables=%7B%22screen_name%22%3A%22{}%22%2C%22withSafetyModeUserFields%22%3Atrue%7D&features=%7B%22hidden_profile_likes_enabled%22%3Afalse%2C%22responsive_web_graphql_exclude_directive_enabled%22%3Atrue%2C%22verified_phone_label_enabled%22%3Afalse%2C%22subscriptions_verification_info_verified_since_enabled%22%3Atrue%2C%22highlights_tweets_tab_ui_enabled%22%3Atrue%2C%22creator_subscriptions_tweet_preview_api_enabled%22%3Atrue%2C%22responsive_web_graphql_skip_user_profile_image_extensions_enabled%22%3Afalse%2C%22responsive_web_graphql_timeline_navigation_enabled%22%3Atrue%7D'.format(
            i[1:]), headers=account_list[0][2]).json()
    try:
        new_follow_id = int(parse('$..rest_id').find(new_user)[0].value)
    except:
        continue
    dic[i] = new_follow_id
print(dic)
