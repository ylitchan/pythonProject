from django.contrib import admin
from .models import *


# Register your models here.
class AlphaInfoAdmin(admin.ModelAdmin):
    list_display = ['tweet_alpha', 'alpha_datetime']
    search_fields = ['alpha_datetime', 'alpha_time']


admin.site.register(LaunchInfo, AlphaInfoAdmin)
