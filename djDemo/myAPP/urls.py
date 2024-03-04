from django.urls import path
import myAPP.views

urlpatterns = [
	# 当指派到本应用的路由一级路由名为hello_world时，调用view.py中的hello_world函数
	path('projects-project',myAPP.views.projects_project),
	path('index',myAPP.views.index),
	path('stocks',myAPP.views.stocks)
]
