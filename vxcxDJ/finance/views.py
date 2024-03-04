from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request,"finance/index.html")

def account(request):
    return render(request,"finance/account.html")

def payInfo(request):
    return render(request,"finance/pay_info.html")