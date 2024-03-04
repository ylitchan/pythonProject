import json
import re
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from pure_pagination import Paginator, PageNotAnInteger
from templatetags.libs.UploadService import UploadService
from templatetags.libs.UrlManager import UrlManager
from upload.models import Image


@csrf_exempt
# Create your views here.
def ueditor(request):
    req = request.GET
    action = req['action'] if 'action' in req else ''

    if action == "config":
        config_path = r"D:\allProjects\pyDemo\vxcxDJ\static\plugins\ueditor\upload_config.json"
        with open(config_path, encoding="utf-8") as fp:
            try:
                config_data = json.loads(re.sub(r'\/\*.*\*/', '', fp.read()))
            except:
                config_data = {}
        return JsonResponse(config_data)

    if action == "uploadimage":
        return uploadImage(request)
    if action == "listimage":
        return listImage(request)

    return "upload"


def uploadImage(request):
    resp = {'state': 'SUCCESS', 'url': '', 'title': '', 'original': ''}
    file_target = request.FILES
    upfile = file_target['upfile'] if 'upfile' in file_target else None
    if upfile is None:
        resp['state'] = "上传失败"
        return JsonResponse(resp)

    ret = UploadService.uploadByFile(upfile)
    if ret['code'] != 200:
        resp['state'] = "上传失败：" + ret['msg']
        return JsonResponse(resp)

    resp['url'] = UrlManager.buildImageUrl(ret['data']['file_key'])
    return JsonResponse(resp)


def listImage(request):
    resp = {'state': 'SUCCESS', 'list': [], 'start': 0, 'total': 0}

    req = request.GET

    start = int(req['start']) if 'start' in req else 0
    page_size = int(req['size']) if 'size' in req else 20

    query = Image.objects.all()
    if start > 0:
        query = query.filter(id__lt=start)

    list = query.order_by('id')[:page_size]
    images = []

    if list:
        for item in list:
            images.append({'url': UrlManager.buildImageUrl(item.file_key)})
            start = item.id
    resp['list'] = images
    resp['start'] = start
    resp['total'] = len(images)
    return JsonResponse(resp)

@csrf_exempt
def uploadPic(request):
    file_target = request.FILES
    upfile = file_target['pic'] if 'pic' in file_target else None
    callback_target = 'window.parent.upload'
    if upfile is None:
        return "<script type='text/javascript'>{0}.error('{1}')</script>".format(callback_target, "上传失败")
    print('================================',upfile)
    ret = UploadService.uploadByFile(upfile)
    if ret['code'] != 200:
        return HttpResponse("<script type='text/javascript'>{0}.error('{1}')</script>".format(callback_target,
                                                                                 "上传失败：" + ret['msg']))

    return HttpResponse("<script type='text/javascript'>{0}.success('{1}')</script>".format(callback_target, ret['data']['file_key']))
