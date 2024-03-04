from django.urls import path,re_path
from account.views import index,info,set,ops


urlpatterns = [
	# 当指派到本应用的路由一级路由名为hello_world时，调用view.py中的hello_world函数
	# re_path(r'index/(?P<page>\d)',index),
	path('index', index),
	path('info', info),
	path('set', set),
	path('ops', ops)
]
