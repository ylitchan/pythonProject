from django.urls import path
from cart.views import setCart,cartIndex


urlpatterns = [
	# 当指派到本应用的路由一级路由名为hello_world时，调用view.py中的hello_world函数
	path('set',setCart),
	path('index',cartIndex),
]
