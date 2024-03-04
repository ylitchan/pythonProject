from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request,"stat/index.html")

def food(request):
    return render(request,"stat/food.html")

def member(request):
    return render(request,"stat/member.html")

def share(request):
    return render(request,"stat/share.html")