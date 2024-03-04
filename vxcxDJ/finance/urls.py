from django.urls import path
from finance.views import index,account,payInfo


urlpatterns = [
	# 当指派到本应用的路由一级路由名为hello_world时，调用view.py中的hello_world函
	path('index', index),
	path('account', account),
	path('pay-info', payInfo),
]
