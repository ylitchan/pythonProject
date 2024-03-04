from django.urls import path
from user.views import login,edit,resetPwd,logout


urlpatterns = [
	# 当指派到本应用的路由一级路由名为hello_world时，调用view.py中的hello_world函数
	path('login',login),
	path('edit', edit),
	path('reset-pwd', resetPwd),
	path('logout', logout)
]
