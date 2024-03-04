from food.models import FoodCat,Food
from member.models import MemberCart,OauthMemberBind
from templatetags.libs.food.FoodService import FoodService
from templatetags.libs.UrlManager import UrlManager
from django.shortcuts import render,redirect
from django.http import HttpResponse,JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from decimal import Decimal
from pure_pagination import Paginator, PageNotAnInteger
# Create your views here.

def foodIndex(request):
    resp = { 'code':200 ,'msg':'操作成功~','data':{} }
    cat_list = FoodCat.objects.filter( status = 1 ).order_by( 'weight')
    data_cat_list = []
    data_cat_list.append({
        'id': 0,
        'name': "全部"
    })
    if cat_list:
        for item in cat_list:
            tmp_data = {
                'id':item.id,
                'name':item.name
            }
            data_cat_list.append( tmp_data  )
    resp['data']['cat_list'] = data_cat_list

    food_list = Food.objects.filter( status = 1 )\
        .order_by( 'total_count','id')[:3]

    data_food_list = []
    if food_list:
        for item in food_list:
            tmp_data = {
                'id':item.id,
                'pic_url':UrlManager.buildImageUrl( item.main_image )
            }
            data_food_list.append( tmp_data )

    resp['data']['banner_list'] = data_food_list
    return JsonResponse( resp )



def foodSearch(request):
    resp = {'code': 200, 'msg': '操作成功~', 'data': {}}
    req = request.GET
    cat_id = int( req['cat_id'] ) if 'cat_id' in req else 0
    mix_kw = str(req['mix_kw']) if 'mix_kw' in req else ''
    p = int( req['p'] ) if 'p' in req else 1

    if p < 1:
        p = 1

    page_size = 10
    offset = ( p - 1 ) * page_size
    query = Food.objects.filter(status=1 )
    if cat_id > 0:
        query = query.filter(cat_id = cat_id)

    if mix_kw:
        rule = query.filter(Q(name=req['mix_kw']) | Q(tags=req['mix_kw']))

    food_list = query.order_by('total_count', 'id')[offset:page_size]

    data_food_list = []
    if food_list:
        for item in food_list:
            tmp_data = {
                'id': item.id,
                'name': "%s"%( item.name ),
                'price': str( item.price ),
                'min_price':str( item.price ),
                'pic_url': UrlManager.buildImageUrl(item.main_image)
            }
            data_food_list.append(tmp_data)
    resp['data']['list'] = data_food_list
    resp['data']['has_more'] = 0 if len( data_food_list ) < page_size else 1
    return JsonResponse(resp)



def foodInfo(request):
    resp = {'code': 200, 'msg': '操作成功~', 'data': {}}
    req = request.GET
    id = int(req['id']) if 'id' in req else 0
    food_info = Food.objects.filter( id = id ).first()
    if not food_info or not food_info.status :
        resp['code'] = -1
        resp['msg'] = "美食已下架"
        return JsonResponse(resp)

    member_info = OauthMemberBind.objects.filter(openid=req['openid']).first()
    cart_number = 0
    if member_info:
        cart_number = MemberCart.objects.filter(member_id=member_info.member_id).count()

    resp['data']['info'] = {
        "id":food_info.id,
        "name":food_info.name,
        "summary":food_info.summary,
        "total_count":food_info.total_count,
        "comment_count":food_info.comment_count,
        'main_image':UrlManager.buildImageUrl( food_info.main_image ),
        "price":str( food_info.price ),
        "stock":food_info.stock,
        "pics":[ UrlManager.buildImageUrl( food_info.main_image ) ]
    }
    resp['data']['cart_number'] = cart_number
    return JsonResponse(resp)