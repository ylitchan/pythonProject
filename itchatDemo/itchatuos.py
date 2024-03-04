import itchat, time
from itchat.content import *
import requests

# itchat.logout()
def floor(slug):
    nft=requests.get('https://app.nfttrack.ai/api/search?q='+slug).json()['data']['collections'][0]['opensea_slug']
    res=requests.get('https://app.nfttrack.ai/api/collection_info/'+nft)
    return nft+'地板：'+str(res.json()['data']['floor_price'])
print(floor('an'))
def qyk(gjc):
    rsp=requests.get('http://api.qingyunke.com/api.php?key=free&appid=0&msg='+gjc)
    return rsp.json()['content']

# @itchat.msg_register([TEXT, MAP, CARD, NOTE, SHARING])
# def text_reply(msg):
#     msg.user.send((qyk(msg.text)))

# @itchat.msg_register([PICTURE, RECORDING, ATTACHMENT, VIDEO])
# def download_files(msg):
#     msg.download(msg.fileName)
#     typeSymbol = {
#         PICTURE: 'img',
#         VIDEO: 'vid', }.get(msg.type, 'fil')
#     return '@%s@%s' % (typeSymbol, msg.fileName)

# @itchat.msg_register(FRIENDS)
# def add_friend(msg):
#     msg.user.verify()
#     msg.user.send((qyk(msg.text)))

@itchat.msg_register(TEXT, isGroupChat=True)
def text_reply(msg):
    print(msg.FromUserName,msg.text)
    if msg.FromUserName == '@@a2bf0e2abbdd8bc5f42e64ab74f09a69f68ab6ea8e34e9a2f1a3c3628a50e7ae' and msg.isAt:
        a=msg.text.replace('@Higan bana ','')
        msg.user.send(floor(a))
    elif msg.FromUserName == '@@35d07ec9a7bcdde5f1a70f00aa5b483b55df6ad6328448117d0caf54a7d3c262' and '牛奶' in msg.text:
        itchat.search_friends(name='女人')[0].send(msg.text)

    # if msg.isAt:
    #     msg.user.send(u'@%s\u2005I received: %s' % (
    #         msg.actualNickName, msg.text))
    # else:
    #     msg.user.send(qyk(msg.text))
itchat.auto_login()
itchat.run(True)

