import decimal
import json

import requests
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from templatetags.libs.member.CartService import CartService
from templatetags.libs.pay.PayService import PayService
from templatetags.libs.UrlManager import UrlManager
from django.views.decorators.csrf import csrf_exempt
from member.models import Member, OauthMemberBind, MemberCart
from food.models import WxShareHistory, Food
from templatetags.libs.member.MemberService import MemberService
from django.db.models import Q
from pure_pagination import Paginator, PageNotAnInteger


# Create your views here.
@csrf_exempt
def orderInfo(request):
    resp = {'code': 200, 'msg': '操作成功~', 'data': {}}
    req = request.POST
    params_goods = req['goods'] if 'goods' in req else None
    member_info = OauthMemberBind.objects.filter(openid=req['openid']).first()
    params_goods_list = []
    if params_goods:
        params_goods_list = json.loads(params_goods)

    food_dic = {}
    for item in params_goods_list:
        food_dic[item['id']] = item['number']

    food_ids = food_dic.keys()
    food_list = Food.objects.filter(id__in=food_ids)
    data_food_list = []
    yun_price = pay_price = decimal.Decimal(0.00)
    if food_list:
        for item in food_list:
            tmp_data = {
                "id": item.id,
                "name": item.name,
                "price": str(item.price),
                'pic_url': UrlManager.buildImageUrl(item.main_image),
                'number': food_dic.get(item.id)
            }
            pay_price = pay_price + decimal.Decimal(item.price * int(food_dic.get(item.id)))
            data_food_list.append(tmp_data)

        # 获取地址
        default_address = {
            "name": "虚幻私塾",
            "mobile": "12345678901",
            "address": "上海市浦东新区XX",
        }

        resp['data']['food_list'] = data_food_list
        resp['data']['pay_price'] = str(pay_price)
        resp['data']['yun_price'] = str(yun_price)
        resp['data']['total_price'] = str(pay_price + yun_price)
        resp['data']['default_address'] = default_address
    return JsonResponse(resp)

@csrf_exempt
def orderCreate(request):
    resp = {'code': 200, 'msg': '操作成功~', 'data': {}}
    req = request.POST
    type = req['type'] if 'type' in req else ''
    note = req['note'] if 'note' in req else ''
    params_goods = req['goods'] if 'goods' in req else None

    items = []
    if params_goods:
        items = json.loads(params_goods)

    if len(items) < 1:
        resp['code'] = -1
        resp['msg'] = "下单失败：没有选择商品~~"
        return JsonResponse(resp)

    member_info = OauthMemberBind.objects.filter(openid=req['openid']).first()
    target = PayService()
    params = {
    }
    resp = target.createOrder(member_info.id, items, params)
    # 如果是来源购物车的，下单成功将下单的商品去掉
    if resp['code'] == 200 and type == "cart":
        print('我要删除购物车')
        CartService.deleteItem(member_info.member_id, items)

    return JsonResponse(resp)
