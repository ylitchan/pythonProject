from django.db import models


# Create your models here.


class UserInfo(models.Model):
    open_id = models.TextField(primary_key=True)
    user_phone = models.TextField(null=True, blank=True)
    user_balance = models.IntegerField(null=True, blank=True)
    user_history = models.TextField(null=True, blank=True)
    user_ts = models.TextField(null=True, blank=True)
    password = models.TextField(null=True, blank=True)
