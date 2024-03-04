import json
from django.shortcuts import render
from rest_framework.response import Response
from threading import Thread
from rest_framework.decorators import api_view
from django.http import HttpResponse
from ishtarApp.models import *
from utils.tools import *
from django.http import StreamingHttpResponse
from django.views.decorators.http import condition


# Create your views here.
def index(request):
    return render(request, 'index.html')


@api_view(['POST'])
def getbalance(request):
    data = request.data
    user_phone = parse('$..user_phone').find(data)[0].value
    user = UserInfo.objects.get(user_phone=user_phone)
    return Response({'code': 200, 'data': {'user_phone': user_phone, 'user_balance': user.user_balance},
                     'msg': '获取用户余额'})


# 微信小程序验证注册api
@api_view(['POST'])
def signin(request):
    data = request.data
    user_phone = parse('$..user_phone').find(data)[0].value
    password = parse('$..password').find(data)[0].value
    try:
        user = UserInfo.objects.get(user_phone=user_phone, password=password)
        print('当前用户', user)
        return Response({'code': 200, 'data': {'user_phone': user_phone}, 'msg': '登录成功'})
    except:
        return Response({'code': 401, 'data': {'user_phone': user_phone}, 'msg': '账号密码不正确'})


@api_view(['POST'])
def getmsg(request):
    data = request.data
    user_phone = parse('$..user_phone').find(data)[0].value
    try:
        user = UserInfo.objects.get(user_phone=user_phone)
        return Response({'code': 200, 'data': {'user_phone': user_phone,
                                               'user_history': claude.chat_conversation_history(user.user_ts)},
                         'msg': '获取历史消息'})
    except:
        return Response({'code': 401, 'data': {'user_phone': user_phone}, 'msg': '请重新登录'})


# 微信小程序注册api
@api_view(['POST'])
def register(request):
    data = request.data
    # open_id = parse('$..open_id').find(data)[0].value
    user_phone = parse('$..user_phone').find(data)[0].value
    password = parse('$..password').find(data)[0].value
    try:
        if UserInfo.objects.filter(user_phone=user_phone):
            return Response({'code': 400, 'data': {'open_id': user_phone}, 'msg': '手机号已被注册,请换个手机号'})
        UserInfo.objects.create(open_id=user_phone, user_phone=user_phone, password=password,
                                user_ts=claude.create_new_chat()['uuid'], user_balance=10,
                                user_history=json.dumps([{}]))
        return Response({'code': 200, 'data': {'open_id': user_phone}, 'msg': '注册成功'})
    except:
        return Response({'code': 400, 'data': {'open_id': user_phone}, 'msg': '注册失败'})


# 微信小程序消息api
@api_view(['POST'])
# @condition(etag_func=None)
def aichat(request):
    data = request.data
    print('客户端消息', data)
    user_phone = parse('$..user_phone').find(data)[0].value
    # 根据open_id查询数据库余额
    user = UserInfo.objects.get(user_phone=user_phone)
    if not user.user_balance:
        return Response({'code': 400, 'data': {'user_phone': user_phone}, 'msg': '余额不足,请联系客服'})
    vx_msg = parse('$..vx_msg').find(data)[0].value
    # user_history = json.loads(user.user_history)
    # 1代表gpt
    if parse('$..type').find(data)[0].value:
        # hf = chat_gpt(
        #     [{"role": "assistant", "content": user_history[-1].get('text', '')}, {"role": "user", "content": vx_msg}])
        for i in range(5):
            try:
                hf = chat_claude(vx_msg, user.user_ts)
                print('获取到gpt回复', hf)
                user.user_balance -= 1
                print('扣款成功')
                user.save()
                break
            except:
                continue
    else:
        pass
    # user_history.append({'state': vx_msg, 'text': parse('$..hf').find(hf)[0].value})
    # user.user_history = json.dumps(user_history)
    return Response(hf)


# 这是用于ISHTARider作为slack应用接收处理消息,返回gpt结果
@api_view(['POST'])
def ishtarider(request):
    if "challenge" in request.data:
        # Respond to the Slack challenge
        return Response({"challenge": request.data["challenge"]})
    Thread(target=ISHTARider, args=[request]).start()
    return Response('ISHTARider')


# 这是用于ISHTAR作为slack用户接收处理消息
@api_view(['POST'])
def ishtar(request):
    # 用于slack bot的webhook验证
    if "challenge" in request.data:
        # Respond to the Slack challenge
        return Response({"challenge": request.data["challenge"]})
    Thread(target=ISHTAR, args=[request]).start()
    return Response('ISHTAR')
