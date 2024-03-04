import requests
from django.shortcuts import render,redirect
from django.http import HttpResponse,JsonResponse
from django.conf import settings
from templatetags.libs.member.MemberService import MemberService
from django.views.decorators.csrf import csrf_exempt
from member.models import Member,OauthMemberBind
from food.models import WxShareHistory
from django.db.models import Q
from pure_pagination import Paginator, PageNotAnInteger
# Create your views here.

@csrf_exempt
def login(request):
    resp = {'code':200, 'msg':'操作成功', 'data':{}}
    req = request.POST
    # code = req['code'] if 'code' in req else ''
    # if not code or len(code) < 1:
    #     resp['code'] = -1
    #     resp['msg'] = '需要code'
    #     return JsonResponse(resp)
    #
    # openid=MemberService.getWeChatOpenId(code)
    openid = req['openid'] if 'openid' in req else ''
    if not openid:
        resp['code'] = -1
        resp['msg'] = '调用微信出错'
        return JsonResponse(resp)
    bind_info = OauthMemberBind.objects.filter(openid=openid, type=1).first()
    if not bind_info:
        nickname = req['nickname'] if 'nickname' in req else ''
        sex = req['gender'] if 'gender' in req else ''
        avatar = req['avatarUrl'] if 'avatarUrl' in req else ''
        model_name = Member()
        model_name.nickname = nickname
        model_name.sex = sex
        model_name.avatar = avatar
        model_name.save()
        model_bind = OauthMemberBind()
        model_bind.member_id = model_name.id
        model_bind.type = 1
        model_bind.openid = openid
        model_bind.extra = ''
        model_bind.save()
        bind_info = model_bind

    member_info = Member.objects.filter(id=bind_info.member_id).first()
    token = "%s#%s" % (MemberService.geneAuthCode(member_info), member_info.id)
    resp['data'] = {'token': token}
    return JsonResponse(resp)

@csrf_exempt
def checkReg(request):
    resp = {'code': 200, 'msg': '操作成功', 'data': {}}
    req = request.POST
    # app.logger.info(req)

    openid = req['openid'] if 'openid' in req else ''
    # if not code or len(code) < 1:
    #     resp['code'] = -1
    #     resp['msg'] = '需要code'
    #     return JsonResponse(resp)
    #
    # openid = MemberService.getWeChatOpenId(code)
    print(openid,'--------------------------')
    if not openid:
        resp['code'] = -1
        resp['msg'] = '調用微信出錯'
        return JsonResponse(resp)

    # 判断是否注册过，没有注册就注册
    bind_info = OauthMemberBind.objects.filter(openid=openid, type=1).first()

    if not bind_info:
        resp['code'] = -1
        resp['msg'] = '未绑定'
        return JsonResponse(resp)

    member_info = Member.objects.filter(id=bind_info.member_id).first()
    if not member_info:
        resp['code'] = -1
        resp['msg'] = '没有查询到绑定信息'
        return JsonResponse(resp)

    token = "%s#%s"%(MemberService.geneAuthCode(member_info),member_info.id)

    return JsonResponse(resp)

@csrf_exempt
def memberShare(request):
    resp = {'code': 200, 'msg': '操作成功~', 'data': {}}
    req = request.POST
    url = req['url'] if 'url' in req else ''
    print('==================')
    member_info = OauthMemberBind.objects.filter(openid=req['openid']).first()
    print(member_info,'==================')
    model_share = WxShareHistory()
    if member_info:
        model_share.member_id = member_info.member_id
    model_share.share_url = url
    model_share.save()
    return JsonResponse(resp)


def memberInfo(request):
    resp = {'code': 200, 'msg': '操作成功~', 'data': {}}
    member_info = OauthMemberBind.objects.filter(openid=request.GET['openid']).first()
    member_info = Member.objects.filter(id=member_info.member_id).first()
    resp['data']['info'] = {
        "nickname":member_info.nickname,
        "avatar_url":member_info.avatar
    }
    return JsonResponse(resp)



