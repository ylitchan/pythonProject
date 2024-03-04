from django.contrib import admin
from .models import *


# Register your models here.
class UserInfoAdmin(admin.ModelAdmin):
    list_display = ['user_phone', 'user_balance']
    search_fields = ['user_phone']


admin.site.register(UserInfo, UserInfoAdmin)
