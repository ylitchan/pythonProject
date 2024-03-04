# -*- coding: utf-8 -*-
import time

from django import template
from django.conf import settings

# register名称不可改
register = template.Library()


@register.filter
def buildUrl(path):
    return path


@register.filter
def buildStaticUrl(path):
    release_version = settings.REALEASE_VERSION
    ver = "%s" % (int(time.time()) if not release_version else release_version)
    path = "/static" + path + "?ver=" + ver
    return path


@register.filter
def buildImageUrl(path):
    app_config = settings.APP
    url = app_config['domain'] + settings.UPLOAD['prefix_url'] + path
    return url


@register.filter
def get_item(a, b):
    return a[b]
