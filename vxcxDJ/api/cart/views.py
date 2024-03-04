import json

import requests
from django.shortcuts import render,redirect
from django.http import HttpResponse,JsonResponse
from django.conf import settings
from templatetags.libs.member.CartService import CartService
from templatetags.libs.UrlManager import UrlManager
from django.views.decorators.csrf import csrf_exempt
from member.models import Member,OauthMemberBind,MemberCart
from food.models import WxShareHistory,Food
from templatetags.libs.member.MemberService import MemberService
from django.db.models import Q
from pure_pagination import Paginator, PageNotAnInteger
# Create your views here.
@csrf_exempt
def setCart(request):
    resp = {'code': 200, 'msg': '添加购物车成功~', 'data': {}}
    req = request.POST
    food_id = int(req['id']) if 'id' in req else 0
    number = int(req['number']) if 'number' in req else 0
    if food_id < 1 or number < 1:
        resp['code'] = -1
        resp['msg'] = "添加购物车失败-1~~"
        return JsonResponse(resp)
    openid = req['openid'] if 'openid' in req else ''
    print(openid, '--------------------------')
    if not openid:
        resp['code'] = -1
        resp['msg'] = '調用微信出錯'
        return JsonResponse(resp)
    member_info =OauthMemberBind.objects.filter(openid=openid).first()
    if not member_info:
        resp['code'] = -1
        resp['msg'] = "添加购物车失败-2~~"
        return JsonResponse(resp)

    food_info = Food.objects.filter(id=food_id).first()
    if not food_info:
        resp['code'] = -1
        resp['msg'] = "添加购物车失败-3~~"
        return JsonResponse(resp)

    if food_info.stock < number:
        resp['code'] = -1
        resp['msg'] = "添加购物车失败,库存不足~~"
        return JsonResponse(resp)

    ret = CartService.setItems(member_id=member_info.member_id, food_id=food_info.id, number=number)
    if not ret:
        resp['code'] = -1
        resp['msg'] = "添加购物车失败-4~~"
        return JsonResponse(resp)

    return JsonResponse(resp)

def cartIndex(request):
    resp = {'code': 200, 'msg': '添加购物车成功~', 'data': {}}
    member_info = OauthMemberBind.objects.filter(openid=request.GET['openid']).first()
    if not member_info:
        resp['code'] = -1
        resp['msg'] = "获取失败，伪登录~~"
        return JsonResponse(resp)
    cart_list = MemberCart.objects.filter( member_id=member_info.member_id)
    data_cart_list = []

    if cart_list:
        food_ids = []
        food_map = {}
        for item in cart_list:
            if not hasattr(item, "food_id"):
                break
            if getattr(item, "food_id") in food_ids:
                continue
            food_ids.append(getattr(item,"food_id"))

        if food_ids and len(food_ids) > 0:
            query = Food.objects.filter(id__in=food_ids)
            for item in query:
                if not hasattr(item, 'id'):
                    break
                food_map[getattr(item, 'id')] = item
        for item in cart_list:
            tmp_food_info = food_map[ item.food_id ]
            tmp_data = {
                "id":item.id,
                "number":item.quantity,
                "food_id": item.food_id,
                "name":tmp_food_info.name,
                "price":str( tmp_food_info.price ),
                "pic_url": UrlManager.buildImageUrl( tmp_food_info.main_image ),
                "active":True
            }
            data_cart_list.append( tmp_data )

    resp['data']['list'] = data_cart_list
    return JsonResponse(resp)


def delCart(request):
    resp = {'code': 200, 'msg': '添加购物车成功~', 'data': {}}
    req = request.POST
    params_goods = req['goods'] if 'goods' in req else None
    items = []
    if params_goods:
        items = json.loads(params_goods)
    if not items or len( items ) < 1:
        return JsonResponse(resp)

    member_info = OauthMemberBind.objects.filter(openid=request.GET['openid']).first()
    if not member_info:
        resp['code'] = -1
        resp['msg'] = "删除购物车失败-1~~"
        return JsonResponse(resp)

    ret = CartService.deleteItem( member_id = member_info.id, items = items )
    if not ret:
        resp['code'] = -1
        resp['msg'] = "删除购物车失败-2~~"
        return JsonResponse(resp)
    return JsonResponse(resp)