import hashlib, base64,random,string,requests,json
from django.conf import settings
print('drcg=======================')
class MemberService():

    @staticmethod
    def geneAuthCode(member_info):
        m = hashlib.md5()
        str = r"%s-%s-%s" % (member_info.id, settings.SECRET_KEY, member_info.status)
        m.update(str.encode("utf-8"))
        return m.hexdigest()

    @staticmethod
    def geneSalt(length = 16):
        keylist = [random.choice((string.ascii_letters+string.digits)) for i in range(length)]
        return ("".join(keylist))

    @staticmethod
    def getWeChatOpenId(code):
        url = "https://api.weixin.qq.com/sns/jscode2session?appid={0}&secret={1}&js_code={2}&grant_type=authorization_code" \
            .format(settings.MINA_APP['appid'], settings.MINA_APP['appkey'], code)

        r = requests.get(url)
        res = r.json()
        openid = res.get('openid',None)
        return openid
