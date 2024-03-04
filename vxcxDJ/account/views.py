from django.shortcuts import render,redirect
from django.conf import settings
from user.models import IfUser
from django.http import HttpResponse,JsonResponse
from pure_pagination import Paginator, PageNotAnInteger
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
# Create your views here.
def index(request):
    req=request.GET
    current_page=req.get('page',1)
    resp_data = {}
    status=int(req.get('status',1))
    if req.get('mix_kw',None):
        query = IfUser.objects.filter(Q(email=req['mix_kw']) | Q(username=req['mix_kw']))
    else:
        query = IfUser.objects.all()
    if status > -1:
        query = query.filter(is_active = status)
    paginator = Paginator(query, 2, request=request)
    try:
        pageInfo = paginator.page(current_page)
    except:
        pageInfo = paginator.page(1)
    pageObject = paginator.page_range
    resp_data['pageInfo'] = pageInfo
    resp_data['pageObject'] = pageObject
    resp_data['search_con'] = req
    resp_data['status_mapping'] = settings.STATUS_MAPPING
    return render(request,"account/index.html", context=resp_data)



def info(request):
    resp_data = {}
    req = request.GET
    info = IfUser.objects.get(id=req['id'])
    if not info:
        return redirect("/account/index")
    resp_data['info'] = info
    return render( request,"account/info.html" , resp_data)

@csrf_exempt
def set(request):
    default_pwd = "******"
    req = request.GET
    uid = req.get("id", 0)
    if request.method == "GET":
        resp_data = {}
        info = None
        if uid:
            info = IfUser.objects.filter(id=uid).first()
        resp_data['info'] = info
        return render(request,"account/set.html", resp_data)
    req=request.POST
    resp = {'code': 200, 'msg': '操作成功', 'data': {}}
    nickname = req['nickname'] if 'nickname' in req else ''
    email = req['email'] if 'email' in req else ''
    username = req['username'] if 'username' in req else ''
    password = req['password'] if 'password' in req else ''

    if nickname is None or len(nickname)<1:
        resp['code']=-1
        resp['msg']='请输入符合规范的姓名'
        return JsonResponse(resp)



    if email is None or len(email)<1:
        resp['code']=-1
        resp['msg']='请输入符合规范的邮箱'
        return JsonResponse(resp)

    if username is None or len(username)<1:
        resp['code']=-1
        resp['msg']='请输入符合规范的登录名'
        return JsonResponse(resp)

    if password is None or len(password)<1:
        resp['code']=-1
        resp['msg']='请输入符合规范的登录密码'
        return JsonResponse(resp)
    has_in = IfUser.objects.filter(username=username)
    print('================',uid)
    if uid:
        user_info = IfUser.objects.filter(id=uid).first()
    else:
        user_info = IfUser()
    if user_info.username != username and has_in:
        resp['code'] = -1
        resp['msg'] = '登录名已存在，更换后再试'
        return JsonResponse(resp)
    user_info.username = username
    user_info.nickname = nickname
    user_info.email = email
    user_info.username = username
    if password != default_pwd:
        user_info.set_password(password)
    user_info.save()

    return JsonResponse(resp)

@csrf_exempt
def ops(request):
    resp = {'code': 200, 'msg': '操作成功', 'data': {}}

    req = request.POST
    id = req['id'] if 'id' in req else 0
    act = req['act'] if 'act' in req else ''

    if not id:
        resp['code'] = -1
        resp['msg'] = '请選擇要操作的賬號'
        return JsonResponse(resp)

    if not act in ["remove", 'recover']:
        resp['code'] = -1
        resp['msg'] = '操作有誤 請重試'
        return JsonResponse(resp)

    user_info = IfUser.objects.filter(id=id).first()
    if not user_info:
        resp['code'] = -1
        resp['msg'] = '指定賬號不存在'
        return JsonResponse(resp)

    if act=="remove":
        user_info.is_active = 0
    elif act=="recover":
        user_info.is_active = 1
    user_info.save()
    return JsonResponse(resp)
