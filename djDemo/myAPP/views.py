import json
import linecache
import random
from django.core import serializers

from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
from myAPP.models import *
from myAPP.thsDemo import p
from myAPP.tweepyDemo import tp
p.daemon=True
p.start()
tp.daemon=True
tp.start()
def projects_project(request):
    # 这里不能直接返回字符串，而是需要将字符串传入到HttpResponse类中，实例化响应类后进行返回
    projects = Projects.objects.all()
    return render(request, "myAPP/projects-project.html",{'projects':projects})
def stocks(request):
    # 这里不能直接返回字符串，而是需要将字符串传入到HttpResponse类中，实例化响应类后进行返回
    stocks = Stocks.objects.all()
    stocks = serializers.serialize('json', queryset=stocks)#序列化之后在js可以还原为对象
    return HttpResponse(stocks)


def index(request):
    # stocks = Stocks.objects.all()
    # stocks_zip = zip([i.code for i in stocks],[i.stock for i in stocks],[i.latest for i in stocks],[i.changeRatio for i in stocks],[i.upperLimit for i in stocks])#,[linecache.getline(r'closeup.txt',random.randrange(1, 9434)) for i in stocks])
    return render(request, "myAPP/index.html")#,{'stock_zip': stocks_zip})

