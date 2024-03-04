from django.urls import path
from member.views import index,info,set


urlpatterns = [
	# 当指派到本应用的路由一级路由名为hello_world时，调用view.py中的hello_world函数
	path('index',index),
	path('info', info),
	path('set', set),
]
