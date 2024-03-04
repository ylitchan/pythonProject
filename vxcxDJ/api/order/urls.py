from django.urls import path
from order.views import orderInfo,orderCreate


urlpatterns = [
	# 当指派到本应用的路由一级路由名为hello_world时，调用view.py中的hello_world函数
	path('info',orderInfo),
	path('create',orderCreate),
]
