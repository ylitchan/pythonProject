import hashlib,base64,random,string
from  django.conf import settings
class UserService():
    @staticmethod
    def geneAuthCode(user_info):
        m  = hashlib.md5()
        str = r"%s-%s-%s-%s" % (user_info.uid, user_info.login_name, user_info.login_pwd, user_info.login_salt)
        m.update(str.encode("utf-8"))
        return m.hexdigest()

    @staticmethod
    def genePwd(pwd):
        m = hashlib.md5(settings.SECRET_KEY.encode("utf-8"))
        m.update(pwd.encode("utf-8"))
        return m.hexdigest()
    @staticmethod
    def geneSalt(length=16):
        keylist = [random.choices((string.ascii_letters+string.digits)) for i in range(length)]
        return ("".join(keylist))
