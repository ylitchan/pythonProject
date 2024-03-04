from django.urls import path
from statt.views import index,share,member,food


urlpatterns = [
	# 当指派到本应用的路由一级路由名为hello_world时，调用view.py中的hello_world函数
	path('index', index),
	path('food', food),
	path('member', member),
	path('share', share),
]
