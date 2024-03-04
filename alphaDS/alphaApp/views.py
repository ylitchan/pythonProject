import time
# Create your views here.
# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from utils.tools import *

@api_view(['POST'])
def newproject(request):
    lookup_fields = request.data.get('lookup_fields', '')
    order_fields = request.data.get('order_fields', '')

    # 校验lookup_fields和order_fields
    if lookup_fields:
        pass
    if order_fields:
        pass

    return Response(
        {"username": "@ust_dao", "FollowedToday": 1, "Followers": 1, "Bio": "UST DAO 牛逼", "Created": "04/22/2023",
         "DiscoveryTime": "2023-04-22"})


@api_view(['POST', 'GET'])
def launching(request):
    if request.method == 'GET':
        page = int(request.GET.get('page', 1))
        pageSize = int(request.GET.get('pageSize', 10))
        account = request.GET.get('account', '')
        start_time = parser.parse(request.GET.get('startTime', time.strftime('%Y-%m-%d')))
        end_time = parser.parse(request.GET.get('endTime', '9999'))
        tag = request.GET.get('tag', '')
        start_index = (page - 1) * pageSize
        end_index = pageSize * page
        alpha = LaunchInfo.objects.filter(alpha_datetime__range=(start_time, end_time), tweet_tag__contains=tag,
                                          tweet_alpha__contains=account).order_by('alpha_datetime')
        total = len(alpha)
        alpha = alpha[start_index:end_index]
        return Response({'code': 0,
                         'result': {'items': [{j.name: getattr(i, j.name) for j in i._meta.fields} for i in alpha],
                                    'total': total},
                         'message': str(start_index) + '~' + str(end_index)})

    elif request.method == 'POST':
        page = request.data.get('page', 1)
        pageSize = request.data.get('pageSize', 10)
        start_index = (page - 1) * pageSize
        end_index = pageSize * page
        alpha = LaunchInfo.objects.order_by('alpha_datetime')
        total = len(alpha)
        alpha = alpha[start_index:end_index]
        return Response({'code': 200,
                         'data': {'alpha': [{j.name: getattr(i, j.name) for j in i._meta.fields} for i in alpha],
                                  'total': total},
                         'msg': str(start_index) + '~' + str(end_index)})
