# -*- coding: utf-8 -*-
import hashlib,time,random,decimal,json
from food.models import Food,FoodSaleChangeLog
from order.models import PayOrder,PayOrderItem
#from common.models.pay.PayOrderCallbackData import PayOrderCallbackData
from templatetags.libs.food.FoodService import FoodService
from django.db import transaction
class PayService():

    def __init__(self):
        pass

    def createOrder(self,member_id,items = None,params = None):
        resp = {'code': 200, 'msg': '操作成功~', 'data': {}}
        pay_price  = decimal.Decimal( 0.00 )
        continue_cnt = 0
        food_ids = []
        for item in items:
            if decimal.Decimal( item['price'] ) < 0 :
                continue_cnt += 1
                continue

            pay_price = pay_price +  decimal.Decimal( item['price'] ) * int( item['number'] )
            food_ids.append( item['id'] )

        if continue_cnt >= len(items ) :
            resp['code'] = -1
            resp['msg'] = '商品items为空~~'
            return resp

        yun_price = params['yun_price'] if params and 'yun_price' in params else 0
        note = params['note'] if params and 'note' in params else ''
        yun_price = decimal.Decimal( yun_price )
        total_price = pay_price + yun_price
        try:
            with transaction.atomic():
                tmp_pay_item = PayOrderItem()
                #为了防止并发库存出问题了，我们枷鎖with_for_update, 这里可以给大家演示下
                tmp_food_list = Food.objects.select_for_update().filter( id__in=food_ids )
                tmp_food_stock_mapping = {}
                for tmp_item in tmp_food_list:
                    tmp_food_stock_mapping[ tmp_item.id ] = tmp_item.stock

                model_pay_order = PayOrder()
                model_pay_order.order_sn = self.geneOrderSn()
                model_pay_order.member_id = member_id
                model_pay_order.total_price = total_price
                model_pay_order.yun_price = yun_price
                model_pay_order.pay_price = pay_price
                model_pay_order.note = note
                model_pay_order.status = -8
                model_pay_order.express_status = -8
                model_pay_order.save()
                # db.session.add( model_pay_order )
                #db.session.flush()
                for item in items:
                    tmp_left_stock =  tmp_food_stock_mapping[ item['id'] ]

                    if decimal.Decimal(item['price']) < 0:
                        continue

                    if int( item['number'] ) > int( tmp_left_stock ):
                        raise Exception( "您购买的这美食太火爆了，剩余：%s,你购买%s~~"%( tmp_left_stock,item['number'] ) )

                    # 刷視頻庫存
                    tmp_ret = Food.objects.filter( id = item['id'] ).update(stock=int(tmp_left_stock) - int(item['number']))
                    if not tmp_ret:
                        raise Exception("下单失败请重新下单")

                    # tmp_pay_item = PayOrderItem()
                    tmp_pay_item.pay_order_id = model_pay_order.id
                    tmp_pay_item.member_id = member_id
                    tmp_pay_item.quantity = item['number']
                    tmp_pay_item.price = item['price']
                    tmp_pay_item.food_id = item['id']
                    tmp_pay_item.note = note
                    # db.session.add( tmp_pay_item )
                    #db.session.flush()

                    FoodService.setStockChangeLog( item['id'],-item['number'],"在线购买" )
                tmp_pay_item.save()
            resp['data'] = {
                'id' : model_pay_order.id,
                'order_sn' : model_pay_order.order_sn,
                'total_price':str( total_price )
            }
        except Exception as e:
            # db.session.rollback()
            print( e )
            resp['code'] = -1
            resp['msg'] = "下单失败请重新下单"
            resp['msg'] = str(e)
            return resp
        return resp

    def geneOrderSn(self):
        m = hashlib.md5()
        sn = None
        while True:
            str = "%s-%s"%( int( round( time.time() * 1000) ),random.randint( 0,9999999 ) )
            m.update(str.encode("utf-8"))
            sn = m.hexdigest()
            if not PayOrder.objects.filter( order_sn = sn  ).first():
                break
        return sn

