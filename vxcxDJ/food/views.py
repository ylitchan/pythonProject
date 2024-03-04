from food.models import FoodCat,Food,FoodStockChangeLog
from templatetags.libs.food.FoodService import FoodService
from django.shortcuts import render,redirect
from django.http import HttpResponse,JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from decimal import Decimal
from pure_pagination import Paginator, PageNotAnInteger
# Create your views here.
def catSet(request):
    if request.method == "GET":
        resp_data={}
        req = request.GET
        id = int(req.get("id", 0))
        info = None
        if id:
            info = FoodCat.objects.filter(id = id).first()
        resp_data['info'] = info
        resp_data['current'] = 'cat-set'
        return render( request,"food/cat_set.html" , resp_data)
    resp = {'code': 200, 'msg': '账户添加成功', 'data': {}}
    req = request.POST
    name = req['name'] if 'name' in req else ''
    weight = int(req['weight']) if ('weight' in req and int(req['weight']) > 0) else 1

    id = req['id'] if 'id' in req else 0
    if name is None or len(name) < 1:
        resp['code'] = -1
        resp['msg'] = "请输入正确的用户名"
        return JsonResponse(resp)

    food_cat_info = FoodCat.objects.filter(id=id).first()

    if food_cat_info:
        model_food_cat = food_cat_info
    else:
        model_food_cat = FoodCat()

    model_food_cat.name = name
    model_food_cat.weight = weight
    model_food_cat.save()

    return JsonResponse(resp)

def cat(request):
    resp_data = {}
    req = request.GET
    if 'status' in req and int(req['status']) > -1:
        query = FoodCat.objects.filter(status = int(req['status']))
    else:
        query=FoodCat.objects.all()

    list = query.order_by('weight', 'id')
    resp_data['list'] = list
    resp_data['search_con'] = req
    resp_data['status_mapping'] = settings.STATUS_MAPPING
    resp_data['current'] = 'cat'

    return render( request,"food/cat.html" , resp_data)

def catOps(request):
    resp = {'code': 200, 'msg': '删除或者恢复成功', 'data': {}}
    req = request.POST
    id = req['id'] if 'id' in req else 0
    act = req['act'] if 'act' in req else ""

    if not id:
        resp['code'] = -1
        resp['msg'] = "请选择要操作的账号"
        return JsonResponse(resp)

    if not act in ["remove", "recover"]:
        resp['code'] = -1
        resp['msg'] = "操作有误，请重试"
        return JsonResponse(resp)

    food_cat_info = FoodCat.objects.filter(id = id).first()
    if not food_cat_info:
        resp['code'] = -1
        resp['msg'] = "分类不存在"
        return JsonResponse(resp)

    if act == "remove":
        food_cat_info.status = 0
    elif act == "recover":
        food_cat_info.status = 1
    food_cat_info.save()

    return JsonResponse(resp)


@csrf_exempt
def set(request):
    if request.method == "GET":
        resp_data = {}
        req = request.GET
        id = int(req.get('id', 0))
        info = Food.objects.filter(id=id).first()
        if info and info.status != 1:
            return redirect("/food/index")
        cat_list = FoodCat.objects.all()
        resp_data['info'] = info
        resp_data['cat_list'] = cat_list
        resp_data['current'] = 'index'
        return render(request,"food/set.html" , resp_data)
    resp = {'code': 200, 'msg': '操作成功~~', 'data': {}}
    req = request.POST
    id = int(req['id']) if 'id' in req and req['id'] else 0
    cat_id = int(req['cat_id']) if 'cat_id' in req else 0
    name = req['name'] if 'name' in req else ''
    price = req['price'] if 'price' in req else ''
    main_image = req['main_image'] if 'main_image' in req else ''
    summary = req['summary'] if 'summary' in req else ''
    stock = int(req['stock']) if 'stock' in req else ''
    tags = req['tags'] if 'tags' in req else ''

    if cat_id < 1:
        resp['code'] = -1
        resp['msg'] = "请选择分类~~"
        return JsonResponse(resp)

    if name is None or len(name) < 1:
        resp['code'] = -1
        resp['msg'] = "请输入符合规范的名称~~"
        return JsonResponse(resp)

    if not price or len(price) < 1:
        resp['code'] = -1
        resp['msg'] = "请输入符合规范的售卖价格~~"
        return JsonResponse(resp)

    price = Decimal(price).quantize(Decimal('0.00'))
    if price <= 0:
        resp['code'] = -1
        resp['msg'] = "请输入符合规范的售卖价格~~"
        return JsonResponse(resp)

    if main_image is None or len(main_image) < 3:
        resp['code'] = -1
        resp['msg'] = "请上传封面图~~"
        return JsonResponse(resp)

    if summary is None or len(summary) < 3:
        resp['code'] = -1
        resp['msg'] = "请输入图书描述，并不能少于10个字符~~"
        return JsonResponse(resp)

    if stock < 1:
        resp['code'] = -1
        resp['msg'] = "请输入符合规范的库存量~~"
        return JsonResponse(resp)

    if tags is None or len(tags) < 1:
        resp['code'] = -1
        resp['msg'] = "请输入标签，便于搜索~~"
        return JsonResponse(resp)

    food_info = Food.objects.filter(id=id).first()
    before_stock = 0
    if food_info:
        model_food = food_info
        before_stock = model_food.stock
    else:
        model_food = Food()
        model_food.status = 1

    model_food.cat_id = cat_id
    model_food.name = name
    model_food.price = price
    model_food.main_image = main_image
    model_food.summary = summary
    model_food.stock = stock
    model_food.tags = tags
    model_food.save()

    FoodService.setStockChangeLog(model_food.id, int(stock) - int(before_stock), "后台修改")
    return JsonResponse(resp)

def index(request):
    req = request.GET
    current_page = req.get('page', 1)
    resp_data = {}
    status = int(req.get('status', 1))
    if req.get('mix_kw', None):
        query = Food.objects.filter(Q(name=req['mix_kw']) | Q(tags=req['mix_kw']))
    else:
        query = Food.objects.all()
    if status > -1:
        query = query.filter(status=int(status))
    if 'cat_id' in req and int( req['cat_id'] ) > 0 :
        query = query.filter(cat_id = int( req['cat_id'] ) )
    paginator = Paginator(query, 2, request=request)
    try:
        pageInfo = paginator.page(current_page)
    except:
        pageInfo = paginator.page(1)
    pageObject = paginator.page_range
    cat_mapping = FoodCat.objects.all()
    ret = {}
    for item in cat_mapping:
        if not hasattr(item, 'id'):
            break
        ret[getattr(item, 'id')] = item.name
    resp_data['pageInfo'] = pageInfo
    resp_data['pageObject'] = pageObject
    resp_data['search_con'] = req
    resp_data['status_mapping'] = settings.STATUS_MAPPING
    resp_data['cat_mapping'] = ret
    resp_data['current'] = 'index'
    return render( request,"food/index.html",resp_data )

def foodSearch(request):
    return

def info(request):
    resp_data = {}
    req = request.GET
    id = int(req.get("id", 0))
    reback_url = "/food/index"

    if id < 1:
        return redirect( reback_url )

    info = Food.objects.filter( id =id ).first()
    if not info:
        return redirect( reback_url )

    stock_change_list = FoodStockChangeLog.objects.filter( food_id = id ).order_by( 'id' )

    resp_data['info'] = info
    resp_data['stock_change_list'] = stock_change_list
    resp_data['current'] = 'index'
    return render( request,"food/info.html",resp_data )