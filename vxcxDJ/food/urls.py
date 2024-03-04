from django.urls import path
from food.views import catSet,cat,catOps,set,index,info


urlpatterns = [
	# 当指派到本应用的路由一级路由名为hello_world时，调用view.py中的hello_world函数
	path('cat-set',catSet),
	path('cat',cat),
	path('cat-ops',catOps),
	path('index', index),
	path('set', set),
	path('info', info),
]
