import requests
from django.shortcuts import render,redirect
from django.http import HttpResponse,JsonResponse
from django.conf import settings
from templatetags.libs.member.MemberService import MemberService
from django.views.decorators.csrf import csrf_exempt
from member.models import Member,OauthMemberBind
from django.db.models import Q
from pure_pagination import Paginator, PageNotAnInteger
# Create your views here.
def index(request):
    resp_data = {}
    req=request.GET
    status=int(req.get('status',1))
    current_page = req.get('page', 1)
    if req.get('mix_kw',None):
        query = Member.objects.filter(Q(nickname=req['mix_kw']) | Q(mobile=req['mix_kw']))
    else:
        query = Member.objects.all()
    if status > -1:
        query = query.filter(status = status)
    paginator = Paginator(query, 1, request=request)
    try:
        pageInfo = paginator.page(current_page)
    except:
        pageInfo = paginator.page(1)
    pageObject = paginator.page_range
    resp_data['pageInfo'] = pageInfo
    resp_data['pageObject'] = pageObject
    resp_data['search_con'] = req
    resp_data['status_mapping'] = settings.STATUS_MAPPING
    resp_data['current'] = 'index'

    return render( request,"member/index.html",resp_data )




def info(request):
    resp_data = {}

    req = request.GET
    id = int(req.get("id", 0))
    rebackUrl = "member/index"
    if id < 1:
        return redirect(rebackUrl)

    info = Member.objects.filter(id = id).first()
    if not info:
        return redirect(rebackUrl)

    resp_data['info'] = info
    resp_data['current'] = 'index'

    return render(request, "member/info.html" ,resp_data)

@csrf_exempt
def set(request):
    if request.method == "GET":
        resp_data = {}

        req = request.GET
        id = int(req.get("id", 0))
        rebackUrl = "member/index"
        if id < 1:
            return redirect(rebackUrl)

        member_info = Member.objects.filter(id=id).first()
        if not member_info:
            return redirect(rebackUrl)

        resp_data['info'] = member_info
        resp_data['current'] = 'index'
        return render( request,"member/set.html",resp_data  )
    resp = {'code': 200, 'msg': '账户添加成功', 'data': {}}
    req = request.POST
    id = req['id'] if 'id' in req else 0
    nickname = req['nickname'] if 'nickname' in req else ''

    if nickname is None or len(nickname) < 1:
        resp['code'] = -1
        resp['msg'] = "请输入正确的用户名"
        return JsonResponse(resp)

    member_info = Member.objects.filter(id=id).first()
    if not member_info:
        resp['code'] = -1
        resp['msg'] = "指定会员不存在"
        return JsonResponse(resp)

    member_info.nickname = nickname
    member_info.save()

    return JsonResponse(resp)


def ops(request):
    resp = {'code': 200, 'msg': '账户添加成功', 'data': {}}
    req = request.POST
    id = req['id'] if 'id' in req else 0
    act = req['act'] if 'act' in req else ''

    if not id:
        resp['code'] = -1
        resp['msg'] = "请选择要操作的账号"
        return JsonResponse(resp)

    if act not in ['remove', 'recover']:
        resp['code'] = -1
        resp['msg'] = "操作有误 青菜此测试"
        return JsonResponse(resp)

    member_info = Member.query.filter_by(id=id).first()
    if not member_info:
        resp['code'] = -1
        resp['msg'] = "指定的会员不存在数据库当中"
        return JsonResponse(resp)


    if act == "remove":
        member_info.status = 0
    elif act == "recover":
        member_info.status = 1

    member_info.save()

    return JsonResponse(resp)
def comment(request):
    return render( request,"members/comment.html" )