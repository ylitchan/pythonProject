from django.urls import path
from apifood.views import foodIndex,foodSearch,foodInfo


urlpatterns = [
	# 当指派到本应用的路由一级路由名为hello_world时，调用view.py中的hello_world函数
	# path('cat-set',catSet),
	path('info',foodInfo),
	path('search',foodSearch),
	path('index', foodIndex),
	# path('set', set),
]
