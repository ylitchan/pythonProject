import asyncio
import aiohttp
import time
import json
import scrapy
import ast
start = time.time()
baseurl = 'https://mobile.twitter.com/i/api/graphql/9rGM7YNDYuiqd0Cb0ZwLJw/Following?variables=%7B%22userId%22%3A%22{id}%22%2C%22count%22%3A20%2C%22{cursor}includePromotedContent%22%3Afalse%2C%22withSuperFollowsUserFields%22%3Atrue%2C%22withDownvotePerspective%22%3Afalse%2C%22withReactionsMetadata%22%3Afalse%2C%22withReactionsPerspective%22%3Afalse%2C%22withSuperFollowsTweetFields%22%3Atrue%7D&features=%7B%22responsive_web_twitter_blue_verified_badge_is_enabled%22%3Afalse%2C%22verified_phone_label_enabled%22%3Afalse%2C%22responsive_web_graphql_timeline_navigation_enabled%22%3Atrue%2C%22unified_cards_ad_metadata_container_dynamic_card_content_query_enabled%22%3Atrue%2C%22tweetypie_unmention_optimization_enabled%22%3Atrue%2C%22responsive_web_uc_gql_enabled%22%3Atrue%2C%22vibe_api_enabled%22%3Atrue%2C%22responsive_web_edit_tweet_api_enabled%22%3Atrue%2C%22graphql_is_translatable_rweb_tweet_is_translatable_enabled%22%3Atrue%2C%22standardized_nudges_misinfo%22%3Atrue%2C%22tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled%22%3Afalse%2C%22interactive_text_enabled%22%3Atrue%2C%22responsive_web_text_conversations_enabled%22%3Afalse%2C%22responsive_web_enhance_cards_enabled%22%3Atrue%7D'
datalist=[]
dataset=set()
semaphore = 5
sem = asyncio.Semaphore(semaphore)

headers = {
    'cookie': 'eu_cn=1; mbox=PC#1750ee752d3c488389676800db08aada.32_0#1724494716|session#822cb106082f4ef08318f4cf5f11db0b#1661251776; _ga_BYKEBDM7DS=GS1.1.1661249915.3.0.1661249915.0.0.0; _ga=GA1.2.864712115.1661059825; _gid=GA1.2.430713795.1667311220; guest_id_marketing=v1:166744179294453011; guest_id_ads=v1:166744179294453011; gt=1588060072369717249; kdt=W8Nipq2n9wjGfMs84QPbzXsaZ8f7lLebOei5p88c; dnt=1; auth_token=b175b0effe3aa5aadf5f12db4209c882dbbd7bc7; personalization_id="v1_srppJgJWu8qvJcPFDbV7hg=="; guest_id=v1:166745827994223011; ct0=590aa83360a26ced3b9b9d83e284aceefde76811bb96e219d3a2890753a60963812047ab26e47753a99d5efad1700a335687c5806c3fe97a5f368fb4d0657591b8c760222eebf87f13875681dc58ef92; att=1-7ReROcc2UEPCUCpgVpqNwU6bsLLgbUSdch93iB27; twid=u=1577862800952930305',
    'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36 Edg/107.0.1418.26',
    'x-csrf-token': '590aa83360a26ced3b9b9d83e284aceefde76811bb96e219d3a2890753a60963812047ab26e47753a99d5efad1700a335687c5806c3fe97a5f368fb4d0657591b8c760222eebf87f13875681dc58ef92',
    'content-type':'application/json',
    'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA'
}
async def request(id,session):
    async with sem:
        cursors = ['']
        cursorbuttons = []
        session = aiohttp.ClientSession()
        async def get():
            #async with session.get(baseurl.format(id=id, cursor=cursors[-1]), proxy='http://127.0.0.1:10810', headers=headers) as response:
            resp = await session.get(baseurl.format(id=id, cursor=cursors[-1]), headers=headers)
            try:
                response = await resp.json()
            except:
                response=await resp.text()
                print(response)
                await asyncio.sleep(930)
                resp = await session.get(baseurl.format(id=id, cursor=cursors[-1]), proxy='http://127.0.0.1:10810',
                               headers=headers)
                response = await resp.json()
            response = response['data']['user']['result']['timeline']['timeline']['instructions'][-1]['entries']
            cursor = response[-2]['content']['value']
            cursorbuttons.append(cursor.split('|')[0])
            cursor = 'cursor%22%3A%22' + cursor.replace('|', '%7C') + '%22%2C%22'
            print(cursor)
            cursors.append(cursor)
            for i in response:
                try:
                    legacy = i['content']['itemContent']['user_results']['result']['legacy']
                        # print('name:', legacy['name'], 'screen_name:', legacy['screen_name'], 'followers_count:',
                        #       legacy['followers_count'])
                    datalist.append(legacy['name'])
                except:
                    continue
            if cursorbuttons[-1] != '0':
                await get()
        # try:
        await get()
        # except:
        #     await session.close()


        await session.close()

async def main():
    session = aiohttp.ClientSession()
    with open('alpha.json', 'r') as alpha:
        alpha = json.load(alpha)
        tasks = [asyncio.ensure_future(request(alpha[id],session)) for id in alpha]
        await asyncio.wait(tasks)
        await session.close()
        print(len(datalist))
        for l in range(len(datalist)):
            num = datalist.count(datalist[l])
            if num > 1:
                dataset.add(str({datalist[l]:num}))
        print(len(dataset))
        for dt in dataset:
            print(dt)
if __name__ == '__main__':
    # with open('alpha.json', 'r') as alpha:
    #     alpha = json.load(alpha)
    #     tasks = [alpha[id] for id in alpha]
    #     for tk in tasks:
    #         asyncio.run(request(tk))
    while True:
        asyncio.run(main())
    # with open('alpha.json','r') as alpha:
    #     alpha = json.load(alpha)
    #     loop = asyncio.get_event_loop()
    #     tasks = [asyncio.ensure_future(request(alpha[id])) for id in alpha]
    # asyncio.run(asyncio.gather(*tasks))
    #     loop.run_until_complete(asyncio.wait(tasks))
        end = time.time()
        print('Cost time:', end - start)
