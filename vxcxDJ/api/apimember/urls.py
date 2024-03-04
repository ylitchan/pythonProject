from django.urls import path
from apimember.views import login,checkReg,memberShare,memberInfo


urlpatterns = [
	# 当指派到本应用的路由一级路由名为hello_world时，调用view.py中的hello_world函数
	path('login',login),
	path('info',memberInfo),
	path('check-reg',checkReg),
	path('share', memberShare),
	# path('set', set),
]
