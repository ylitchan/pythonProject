from django.db import models
from django.conf import settings

# Create your models here.

class OauthMemberBind(models.Model):
    member_id = models.IntegerField()
    client_type = models.TextField()
    type = models.IntegerField()
    openid = models.TextField()
    unionid = models.TextField()
    extra = models.TextField()
    updated_time = models.DateTimeField(auto_now=True)
    created_time = models.DateTimeField(auto_now_add=True)


class Member(models.Model):
    nickname = models.TextField()
    mobile = models.TextField()
    sex = models.IntegerField()
    avatar = models.TextField()
    reg_ip = models.TextField()
    status = models.IntegerField(default=1)
    updated_time = models.DateTimeField(auto_now=True)
    created_time = models.DateTimeField(auto_now_add=True)

    @property
    def status_desc(self):
        return settings.STATUS_MAPPING[str(self.status)]

    @property
    def sex_desc(self):
        sex_mapping = {
            "0": "未知",
            "1": "男",
            "2": "女"
        }
        return sex_mapping[str(self.sex)]



class MemberCart(models.Model):
    member_id = models.IntegerField()
    food_id = models.IntegerField()
    quantity = models.IntegerField()
    updated_time = models.DateTimeField(auto_now=True)
    created_time = models.DateTimeField(auto_now_add=True)
