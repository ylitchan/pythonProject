import asyncio
import zlib
# from aiowebsocket.converses import AioWebSocket
import json
import aiohttp

remote = 'wss://gateway.dcDemo.gg/?encoding=json&v=9&compress=zlib-stream'
roomid = '271744'
headers = {'Accept-Encoding': 'gzip, deflate, br',
           'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
           'Cache-Control': 'no-cache',
           'Connection': 'Upgrade',
           'Host': 'gateway.dcDemo.gg',
           'Origin': 'https://discord.com',
           'Pragma': 'no-cache',
           'Sec-WebSocket-Extensions': 'permessage-deflate; client_max_window_bits',
           'Sec-WebSocket-Key': 'eMjhkNaeB7zlbSAKNBBRuA==',
           'Sec-WebSocket-Version': '13',
           'Upgrade': 'websocket',
           'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Edg/107.0.1418.26'}
data_raw = {"op": 2, "d": {"token": "MTAxNzAzNjA0MjU4NDQ2OTUyNg.GSqxKK.JVzh1DESAXCYKAuz0OMhZCTVjshoQEkGbZ7oIc",
                           "capabilities": 1021,
                           "properties": {"os": "Windows", "browser": "Chrome", "device": "", "system_locale": "zh-CN",
                                          "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Edg/107.0.1418.26",
                                          "browser_version": "107.0.0.0", "os_version": "10", "referrer": "",
                                          "referring_domain": "", "referrer_current": "",
                                          "referring_domain_current": "", "release_channel": "stable",
                                          "client_build_number": 156540, "client_event_source": "null"},
                           "presence": {"status": "online", "since": 0, "activities": [], "afk": "false"},
                           "compress": "false",
                           "client_state": {"guild_hashes": {}, "highest_last_message_id": "0", "read_state_version": 0,
                                            "user_guild_settings_version": -1, "user_settings_version": -1,
                                            "private_channels_version": "0"}}}

# data_raw = data_raw.format(headerLen=hex(27 + len(roomid))[2:],
# roomid=''.join(map(lambda x: hex(ord(x))[2:], list(roomid))))
data_raw2 = {"op": 4, "d": {"guild_id": "null", "channel_id": "null", "self_mute": "true", "self_deaf": "false",
                            "self_video": "false"}}


async def startup():
    async with aiohttp.ClientSession().ws_connect(url=remote, proxy='http://127.0.0.1:10810', headers=headers) as aws:
        print('握手')
        # converse = aws.manipulator
        await aws.send_json(data_raw)

        tasks = [receDM(aws),sendHeartBeat(aws)]
        await asyncio.wait(tasks)





async def sendHeartBeat(websocket):
    d = 24
    while True:
        hb = {"op": 1, "d": d}
        await asyncio.sleep(40)
        await websocket.send_json(hb)
        print('[Notice] Sent HeartBeat.',d)
        d += 1


async def receDM(websocket):
    for i in range(2):
        recv_text = await websocket.receive()
        printDM(recv_text)
    await websocket.send_json(data_raw2)
    # await websocket.send_json('{"op":13,"d":{"channel_id":"1017036914383126549"}}')

    # if recv_text == None:
    #     recv_text = b'\x00\x00\x00\x1a\x00\x10\x00\x01\x00\x00\x00\x08\x00\x00\x00\x01{"code":0}'
    while 1:
        print('-----------------------------------')
        recv_text = await websocket.receive_bytes()
        printDM(recv_text)
        # data = zlib.decompress(recv_text,16+zlib.MAX_WBITS)
        # print(data )


# 将数据包传入：
def printDM(data):
    print('这是原始data', data)
    # # 获取数据包的长度，版本和操作类型
    # packetLen = int(data[:4].hex(), 16)
    # ver = int(data[6:8].hex(), 16)
    # op = int(data[8:12].hex(), 16)
    #
    # # 有的时候可能会两个数据包连在一起发过来，所以利用前面的数据包长度判断，
    # if (len(data) > packetLen):
    #     printDM(data[packetLen:])
    #     data = data[:packetLen]
    #
    # # 有时会发送过来 zlib 压缩的数据包，这个时候要去解压。
    # if (ver == 2):
    #     data = zlib.decompress(data[16:])
    #     print('这是解压后的data',data)
    #     printDM(data)
    #     return
    #
    # # ver 为1的时候为进入房间后或心跳包服务器的回应。op 为3的时候为房间的人气值。
    # if (ver == 1):
    #     if (op == 3):
    #         print('[RENQI]  {}'.format(int(data[16:].hex(), 16)))
    #     return
    #
    #
    # # ver 不为2也不为1目前就只能是0了，也就是普通的 json 数据。
    # # op 为5意味着这是通知消息，cmd 基本就那几个了。
    # if (op == 5):
    #     try:
    #         jd = json.loads(data[16:].decode('utf-8', errors='ignore'))
    #         print('这是json',jd)
    #         # if (jd['cmd'] == 'DANMU_MSG'):
    #         #     print('[DANMU] ', jd['info'][2][1], ': ', jd['info'][1])
    #         # elif (jd['cmd'] == 'SEND_GIFT'):
    #         #     print('[GITT]', jd['data']['uname'], ' ', jd['data']['action'], ' ', jd['data']['num'], 'x',
    #         #           jd['data']['giftName'])
    #         # elif (jd['cmd'] == 'LIVE'):
    #         #     print('[Notice] LIVE Start!')
    #         # elif (jd['cmd'] == 'PREPARING'):
    #         #     print('[Notice] LIVE Ended!')
    #         # else:
    #         #     print('[OTHER] ', jd['cmd'])
    #     except Exception as e:
    #         pass


if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(startup())
    except Exception as e:
        print('退出', e)
