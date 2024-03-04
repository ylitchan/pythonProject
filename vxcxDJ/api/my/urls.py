from django.urls import path
from my.views import myOrderList,myCommentList


urlpatterns = [
	# 当指派到本应用的路由一级路由名为hello_world时，调用view.py中的hello_world函数
	path('order',myOrderList),
	path('comment/list',myCommentList),
]
