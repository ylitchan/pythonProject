from django.contrib import admin

# Register your models here.账号admin密码123456
# 导入模型
from myAPP.models import *

admin.site.register(Stocks)
admin.site.register(Projects)