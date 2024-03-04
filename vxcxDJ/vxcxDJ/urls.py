"""vxcxDJ URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    path('admin/', admin.site.urls),
# 将URL分配到对应的APP当中进行二级路由,这里是将其分配到blob.urls中
    path("api/",include("api.urls")),
    path("user/", include("user.urls")),
    path("", include("index.urls")),
    path("account/", include("account.urls")),
    path("upload/", include("upload.urls")),
    path("food/", include("food.urls")),
    path("member/", include("member.urls")),
    path("finance/", include("finance.urls")),
    path("stat/", include("statt.urls")),
]
