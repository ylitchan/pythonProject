# -*- coding: utf-8 -*-
import time
from django.conf import settings

class UrlManager(object):
    def __init__(self):
        pass

    @staticmethod
    def buildUrl( path ):
        return path

    @staticmethod
    def buildStaticUrl(path):
        release_version = settings.REALEASE_VERSION
        ver = "%s"%(int(time.time()) if not release_version else release_version)
        path =  "/static" + path + "?ver=" + ver
        return UrlManager.buildUrl( path )

    @staticmethod
    def buildImageUrl( path ):
        app_config = settings.APP
        url = app_config['domain'] + settings.UPLOAD['prefix_url'] + path
        return url
