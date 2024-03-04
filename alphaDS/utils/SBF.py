from tools import *


def get_list_members(ids: list):
    sbfilter = ScalableBloomFilter(mode=ScalableBloomFilter.SMALL_SET_GROWTH)
    # already = []
    for list_id in ids:
        member = client_tweet.get_list_members(list_id, pagination_token=None, user_auth=True)
        next_token = member.meta.get('next_token')
        for i in member.data:
            sbfilter.add(i.id)
        # already.extend([i.id for i in member.data])
        # print('列表数量', len(already))
        while next_token:
            try:
                member = client_tweet.get_list_members(list_id, pagination_token=next_token)
                next_token = member.meta.get('next_token')
                for i in member.data:
                    sbfilter.add(i.id)
                # already.extend([i.id for i in member.data])
                # print('获取成功', len(already))
                time.sleep(60)
            except:
                print('获取错误')
                time.sleep(900)
                continue
        time.sleep(60)
    # with open('listMembers.json', 'w') as f:
    #     json.dump(list(set(already)), f)
    with open('sbfilterMember', 'wb') as f:
        sbfilter.tofile(f)


if __name__ == '__main__':
    # get_list_members(['1639838455760035840'])
    with open('sbflist', 'rb') as f:
        sbfilter = ScalableBloomFilter(mode=ScalableBloomFilter.SMALL_SET_GROWTH).fromfile(f)
    account_list = ACCOUNT_LIST
    with open('listMembers.json', 'r') as f:
        members = json.load(f)
    for i in members:
        index = 0
        if not sbfilter.add(i):
            added = session.post('https://twitter.com/i/api/graphql/27lfFOrDygiZs382QLttKA/ListAddMember',
                                 headers=account_list[index][2],
                                 json={
                                     "variables": {

                                         "listId": '1676556768862953473',
                                         "userId": i
                                     },
                                     "features": {
                                         "rweb_lists_timeline_redesign_enabled": True,
                                         "responsive_web_graphql_exclude_directive_enabled": True,
                                         "verified_phone_label_enabled": False,
                                         "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                                         "responsive_web_graphql_timeline_navigation_enabled": True
                                     },
                                     "queryId": "27lfFOrDygiZs382QLttKA"
                                 }).json()
            print(i)
            index += 1
            if index == len(ACCOUNT_LIST):
                index = 0
            with open('sbflist', 'wb') as f:
                sbfilter.tofile(f)
            time.sleep(300)
