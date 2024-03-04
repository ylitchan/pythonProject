from pyrogram import Client
from tools import *

proxy = {
    "scheme": "http",  # "socks4", "socks5" and "http" are supported
    "hostname": "127.0.0.1",
    "port": 10810,
    # "username": "username",
    # "password": "password"
}
app = Client("my_account", os.getenv('api_id'), os.getenv('api_hash'), proxy=proxy)


# a= [
#             "@0xdantrades",
#             "@0xGeeGee",
#             "@0xon99",
#             "@0xsn0wball",
#             "@0xYelf",
#             "@2lambro",
#             "@ApeOClock",
#             "@ArbitrumNewsDAO",
#             "@Arron_finance",
#             "@ChadCaff",
#             "@CJCJCJCJ_",
#             "@criptopaul",
#             "@crypt0detweiler",
#             "@cryptamurai",
#             "@crypto_saint",
#             "@CryptoGangster6",
#             "@CryptoK63140864",
#             "@CryptoKaduna",
#             "@cryptomemez",
#             "@dawsboss888",
#             "@defi_antcrypto",
#             "@doctorDefi2020",
#             "@DoloNFT",
#             "@duke_rick1",
#             "@Ed_x0101",
#             "@EinsteinYipie",
#             "@Ekonomeest",
#             "@ElCryptoDoc",
#             "@EricCryptoman",
#             "@EricG_Crypto",
#             "@FedAgentAaron",
#             "@FungiAlpha",
#             "@gemCrawler",
#             "@hellf17",
#             "@Henry_VuQuangDu",
#             "@Hoangarthur2",
#             "@I_am_patrimonio",
#             "@ilovegains",
#             "@InternDAO",
#             "@KadunaGems",
#             "@l2_dariusking",
#             "@lalalallsoosos",
#             "@lawrenx_",
#             "@LeNeutron",
#             "@LoveKeykey1",
#             "@Luyaoyuan1",
#             "@MiddleChildPabk",
#             "@modab_dot_tv",
#             "@MohammedTunkar4",
#             "@monosarin",
#             "@multichainchad",
#             "@o_ponle",
#             "@panoskras",
#             "@RaccoonHKG",
#             "@RASOKA_ETH",
#             "@realdogen",
#             "@RomAin11515879",
#             "@RvCrypto",
#             "@Sajuio8",
#             "@skiesyyyy",
#             "@SlukaOzella",
#             "@sululukz99",
#             "@sung_crypto",
#             "@SweetPeaCrypto",
#             "@Tanaka_L2",
#             "@The_1legendd",
#             "@TheRealGapper",
#             "@xiaowuDD666",
#             "@yakuza_crypto",
#             "@Yamatoeth",
#             "@yutiancoin",
#             "@yuyue_chris",
#             "@zkSync_Research"
#         ]

@app.on_message()
async def raw(client, message):
    print(message)
    is_admin = False
    name = ''
    chat_id = ''
    chat_username = 'UST_DAO'
    user_id = '-1623440846'
    if hasattr(message, 'from_user') and message.from_user:
        user_id = str(message.from_user.id)
        for i in [message.from_user.first_name, message.from_user.last_name]:
            if i:
                name += i
    if hasattr(message, 'chat'):
        try:
            is_admin = message.chat.permissions.can_pin_messages
            chat_username = message.chat.username
            chat_id = str(message.chat.id)
        except:
            pass
    elif hasattr(message, 'sender_chat'):
        try:
            is_admin = message.sender_chat.permissions.can_pin_messages
            chat_username = message.sender_chat.username
            chat_id = str(message.chat.id)
        except:
            pass
    # print(chat_id,message.text)
    # tt的消息
    if user_id == '6129189645' and message.text:
        # print(message)
        # print(time.strftime('%Y-%m-%d %H:%M:%S %Z %A'), '新增關注', message.text)
        # await app.send_message(6129189645, a.pop())
        # print(message.chat.title, message.text, message.date.strftime("%Y-%m-%d %H:%M:%S"),
        #       message.id, name,
        #       chat_username, user_id, sep='\n')
        # if message.text:
        # 提取新增關注的username
        new_follow = re.findall(r'@[A-Za-z0-9_]+', message.text)
        total = len(new_follow)
        if total > 1:
            # while True:
            #     try:
            # for i in range(total // 100 + 1):
            # new_follow = client_tweet.get_user(username=new_follow[1][1:],
            #                                    user_fields=["profile_image_url", "public_metrics",
            #                                                 'created_at',
            #                                                 'description']).data
            # for m in new_follow:
            producer.publish('q_add', new_follow[1][1:])
            # q_add.put(new_follow[1][1:])
            print(time.strftime('%Y-%m-%d %H:%M:%S %Z %A'), '新增關注', new_follow[1][1:])
            # [new_follow.id, new_follow.profile_image_url, new_follow.public_metrics, new_follow.created_at,
            #  new_follow.description])
            #     break
            # except:
            #     continue
            # q_alpha.put('tg_alpha',
            #             [message.chat.title, message.text, message.date.strftime("%Y-%m-%d %H:%M:%S %Z %A"), message.id,
            #              name,
            #              chat_username, user_id])
    # tg邀请
    elif message.chat.title == 'TG invite' and message.text and message.text.startswith('https://t.me/'):
        try:
            print(time.strftime('%Y-%m-%d %H:%M:%S %Z %A'), bool(await app.join_chat(message.text)))
        except:
            print(time.strftime('%Y-%m-%d %H:%M:%S %Z %A'), bool(await app.join_chat(message.text.split('/')[-1])))
    # 发射信息
    elif is_admin and message.text and user_id != '5995779313':
        print(time.strftime('%Y-%m-%d %H:%M:%S %Z %A'), '管理员消息',
              [message.chat.title, message.text, message.date.strftime("%Y-%m-%d %H:%M:%S"), message.id, name,
               chat_username, user_id, is_admin])
        # await app.send_message(-1001982993052, message.chat.title + '\n' + message.date.strftime(
        #     "%Y-%m-%d %H:%M:%S") + '\n' + message.text)


if __name__ == '__main__':
    # q_add = queue.Queue()
    Thread(target=add_member, args=[], daemon=True).start()
    app.run()
