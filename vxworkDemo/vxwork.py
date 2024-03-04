import time
from flask import Flask, request



sToken = 'xxxx'  # 对应上图的Token
sEncodingAESKey = 'xxxx'  # 对应上图的EncodingAESKey
sReceiveId = 'xxxx'  # 对应企业ID，即corpid
wxcpt = WXBizMsgCrypt(sToken, sEncodingAESKey, sReceiveId)

app = Flask(__name__)


@app.route('/vxworkbot/', methods=['GET', 'POST'])
def robot():
    msg_signature = request.args.get('msg_signature')  # 企业微信加密签名
    timestamp = request.args.get('timestamp')  # 时间戳
    nonce = request.args.get('nonce')  # 随机数
    echostr = request.args.get('echostr')  # 加密字符串

    # 验证URL有效性
    if request.method == 'GET':
        ret, sReplyEchoStr = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
        if ret == 0:
            return sReplyEchoStr
        else:
            return 'ERR: VerifyURL ret:' + str(ret)

    # 接收消息
    if request.method == 'POST':
        ret, xml_content = wxcpt.DecryptMsg(request.data, msg_signature, timestamp, nonce)
        if ret == 0:
            root = ET.fromstring(xml_content)
            print(xml_content)
            to_user_name = root.find('ToUserName').text
            from_user_name = root.find('FromUserName').text
            create_time = root.find('CreateTime').text
            msg_type = root.find('MsgType').text
            content = root.find('Content').text
            msg_id = root.find('MsgId').text
            agent_id = root.find('AgentID').text
            print(content)
            # return content

            # 被动回复
            create_time = timestamp = str(int(time.time()))
            content = content.replace('吗', '').replace('?', '!').replace('？', '！')
            sReplyMsg = f'<xml><ToUserName>{to_user_name}</ToUserName><FromUserName>{from_user_name}</FromUserName><CreateTime>{create_time}</CreateTime><MsgType>text</MsgType><Content>{content}</Content><MsgId>{msg_id}</MsgId><AgentID>{agent_id}</AgentID></xml>'
            ret, sEncryptMsg = wxcpt.EncryptMsg(sReplyMsg, nonce, timestamp)
            if ret == 0:
                pass
            else:
                return 'ERR: EncryptMsg ret: ' + str(ret)
            return sEncryptMsg
        else:
            return 'ERR: DecryptMsg ret:' + str(ret)


if __name__ == '__main__':
    app.run('127.0.0.1',8999)
