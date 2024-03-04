from django.db import models
from django.conf import settings
# Create your models here.
class PayOrder(models.Model):
    order_sn = models.TextField()
    member_id = models.IntegerField()
    total_price = models.FloatField()
    yun_price = models.FloatField()
    pay_price = models.FloatField()
    pay_sn = models.TextField()
    prepay_id = models.TextField()
    note = models.TextField()
    status = models.IntegerField()
    express_status =  models.IntegerField()
    express_address_id =  models.IntegerField(default=1)
    express_info =  models.IntegerField(default=1)
    comment_status =  models.IntegerField(default=1)
    pay_time = models.DateTimeField(auto_now=True)
    updated_time = models.DateTimeField(auto_now=True)
    created_time = models.DateTimeField(auto_now_add=True)


    @property
    def pay_status(self):
        tmp_status = self.status
        if self.status == 1:
            tmp_status = self.express_status
            if self.express_status == 1 and self.comment_status == 0:
                tmp_status = -5
            if self.express_status == 1 and self.comment_status == 1:
                tmp_status = 1
        return tmp_status

    @property
    def status_desc(self):
        return settings.PAY_STATUS_DISPLAY_MAPPING[ str( self.pay_status )]

    @property
    def order_number(self):
        order_number = self.created_time.strftime("%Y%m%d%H%M%S")
        order_number = order_number + str(self.id).zfill(5)
        return order_number

class PayOrderCallbackDatum(models.Model):
    pay_order_id = models.IntegerField(default=1)
    pay_data = models.TextField()
    refund_data = models.TextField()
    updated_time = models.DateTimeField(auto_now=True)
    created_time = models.DateTimeField(auto_now_add=True)

class PayOrderItem(models.Model):

    pay_order_id = models.IntegerField(default=1)
    member_id = models.IntegerField()
    quantity = models.IntegerField()
    price = models.FloatField()
    food_id = models.IntegerField()
    note = models.TextField()
    status = models.IntegerField(default=1)
    updated_time = models.DateTimeField(auto_now=True)
    created_time = models.DateTimeField(auto_now_add=True)