from django.shortcuts import render,redirect
from  django.conf import settings
from django.http import HttpResponse,JsonResponse
from user.models import IfUser
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from templatetags.libs.user.UserService import UserService
# Create your views here.
from django.views.decorators.csrf import csrf_exempt
@csrf_exempt
def login(request):
    if request.method == "GET":
        return render( request,"user/login.html")
    login_name = request.POST['login_name'] if 'login_name' in request.POST else ''
    login_pwd = request.POST['login_pwd'] if 'login_pwd' in request.POST else ''
    resp = {'code':200, 'msg':'登录成功', 'data':{}}
    if login_name is None or len(login_name)<1:
        resp['code']=-1
        resp['msg']="请输入正确的登录用户名~"
        return JsonResponse(resp)

    if login_pwd is None or len(login_pwd)<1:
        resp['code']=-1
        resp['msg']="请输入正确的登录密码~"
        return JsonResponse(resp)

    user_info = auth.authenticate(request,username=login_name,password=login_pwd)
    if not user_info:
        resp['code'] = -1
        resp['msg'] = "请输入正确的登录用户名和密码"
        return JsonResponse(resp)
    auth.login(request, user_info)
    return JsonResponse(resp)
@csrf_exempt
def edit(request):
    if request.method == "GET":
        return render( request,"user/edit.html" ,context={'current':'edit'})

    resp = {'code':200,'msg':'操作成功', 'data':{}}

    req = request.POST
    nickname = req['nickname'] if 'nickname' in req else ''
    email = req['email'] if 'email' in req else ''

    if nickname is None or len(nickname)<1:
        resp['code']=-1
        resp['msg']='请输入符合规范的姓名'
        return JsonResponse(resp)

    if email is None or len(email)<1:
        resp['code']=-1
        resp['msg']='请输入符合规范的邮箱'
        return JsonResponse(resp)
    print('================',request.user)
    IfUser.objects.filter(username=request.user).update(nickname=nickname,email=email)
    return JsonResponse(resp)
@csrf_exempt
@login_required()
def resetPwd(request):
    if request.method == "GET":
        return render( request,"user/reset_pwd.html",context={'current':'reset-pwd'} )
    resp = {'code': 200, 'msg': '操作成功', 'data': {}}

    req = request.POST
    old_password = req['old_password'] if 'old_password' in req else ''
    new_password = req['new_password'] if 'new_password' in req else ''

    if old_password is None or len(old_password) < 6:
        resp['code'] = -1
        resp['msg'] = '请输入符合规范的原密码'
        return JsonResponse(resp)

    if new_password is None or len(new_password) < 6:
        resp['code'] = -1
        resp['msg'] = '请输入符合规范的修改后的密码'
        return JsonResponse(resp)

    if old_password == new_password:
        resp['code'] = -1
        resp['msg'] = '密码相同，请再次输入'
        return JsonResponse(resp)
    user_info = IfUser.objects.get(username=request.user)
    user_info.set_password(new_password)
    user_info.save()
    #更新session
    user_info = auth.authenticate(request, username=request.user, password=new_password)
    auth.login(request, user_info)
    return JsonResponse(resp)

def logout(request):
    auth.logout(request)
    return redirect('http://127.0.0.1:8000/user/login')