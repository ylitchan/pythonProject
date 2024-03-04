from django.db import models
from django.conf import settings
# Create your models here.
class Food(models.Model):
    cat_id = models.IntegerField()
    name = models.TextField()
    price = models.FloatField()
    main_image = models.TextField()
    summary = models.TextField()
    stock = models.IntegerField()
    tags = models.TextField()
    status = models.IntegerField()
    month_count = models.IntegerField(default=0)
    total_count = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)
    updated_time = models.DateTimeField(auto_now=True)
    created_time = models.DateTimeField(auto_now_add=True)

class FoodCat(models.Model):
    name = models.TextField()
    weight = models.IntegerField()
    status = models.IntegerField()
    updated_time = models.DateTimeField(auto_now=True)
    created_time = models.DateTimeField(auto_now_add=True)
    @property
    def status_desc(self):
        return settings.STATUS_MAPPING[str(self.status)]

class FoodSaleChangeLog(models.Model):
    food_id = models.IntegerField()
    quantity = models.IntegerField()
    price = models.FloatField()
    member_id = models.IntegerField()
    created_time = models.DateTimeField(auto_now_add=True)

class FoodStockChangeLog(models.Model):
    food_id = models.IntegerField()
    unit = models.IntegerField()
    total_stock = models.IntegerField()
    note = models.TextField()


class WxShareHistory(models.Model):
    member_id = models.IntegerField()
    share_url = models.TextField()
    created_time = models.DateTimeField(auto_now_add=True)
