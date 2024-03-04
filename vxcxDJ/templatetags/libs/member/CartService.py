# -*- coding: utf-8 -*-
import hashlib,requests,random,string,json
from member.models import MemberCart
class CartService():
    @staticmethod
    def setItems( member_id = 0,food_id = 0,number = 0 ):
        if member_id < 1 or food_id < 1 or number < 1:
            return False
        cart_info = MemberCart.objects.filter( food_id = food_id, member_id= member_id ).first()
        if cart_info:
            model_cart = cart_info
        else:
            model_cart = MemberCart()
            model_cart.member_id = member_id

        model_cart.food_id = food_id
        model_cart.quantity = number
        model_cart.save()
        return True

    @staticmethod
    def deleteItem(member_id=0, items=None):
        if member_id < 1 or not items:
            return False
        for item in items:
            MemberCart.objects.filter(food_id=item['id'], member_id=member_id).delete()
        return True

