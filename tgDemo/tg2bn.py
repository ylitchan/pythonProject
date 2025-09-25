# @Date: 2024/3/6
# @Author: ylitchan
# @Source: rdti_crawl_defense
# @Site:
import re
from pyrogram import Client
import requests
from datetime import datetime
import os
import hashlib
import base64
from enum import auto
import sys
# 添加项目根目录到系统路径
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from tokenDemo.autoBN import AUTOBN


api_id = 20214904
api_hash = "9e4d64ec1b5a77c416b4e5522ce8d325"
app = Client("my_account", api_id, api_hash)

# @app.on_raw_update()
# async def handle_raw(_, update, users, chats):
#     print(update, flush=True)
#     async for i in _.get_chat_history(-1002651333064, limit=5):
#         print(i, flush=True)


def handle_msg(message):
    print(message, flush=True)
    title = message.chat.title if message.chat else ""
    channel_id = message.chat.id if message.chat else 0
    username = message.chat.username if (
        message.chat and message.chat.username) else ""
    if title in ['实盘监控【 熬鹰 | 风寻 | 不懂 】'] or channel_id == -1002651333064 or username == 'allin88888888':
        text = message.text or ''
        autobn.send_msg(text)
        if '【熬鹰资本聪明钱】' in text:
            side = re.findall('开仓|加仓|减仓|平仓', text)[0]
            symbol = re.findall('【币种】.*?(\w+USDT).*?\n', text)[0]
            price = float(re.findall('【开仓价】.*?(\d+(?:\.\d+)?).*?\n', text)[0])
            positionSide = re.findall('【方向】(.*?)\n', text)[0]
            autobn.send_msg(f'==={symbol}{side}===\n开仓价:{price}')
            if '空' in positionSide:
                positionSide = 'SHORT'
                if side == '减仓':
                    autobn.close_bn_position(
                        symbol, "BUY", positionSide, price, close_ratio=0.5)
                elif side == '平仓':
                    autobn.close_bn_position(
                        symbol, "BUY", positionSide, price, close_ratio=1)
                elif side == '加仓':
                    autobn.open_bn_position(symbol, 'SELL', positionSide)
                elif side == '开仓':
                    autobn.open_bn_position(symbol, 'SELL', positionSide)
            elif '多' in positionSide:
                positionSide = 'LONG'
                if side == '减仓':
                    autobn.close_bn_position(
                        symbol, "SELL", positionSide, price, close_ratio=0.5)
                elif side == '平仓':
                    autobn.close_bn_position(
                        symbol, "SELL", positionSide, price, close_ratio=1)
                elif side == '加仓':
                    autobn.open_bn_position(symbol, 'BUY', positionSide)
                elif side == '开仓':
                    autobn.open_bn_position(symbol, 'BUY', positionSide)


@app.on_edited_message()
async def on_edit(client, message):
    print('on_edited_message', flush=True)
    handle_msg(message)


@app.on_message()
async def raw(client, message):
    print('on_message', flush=True)
    handle_msg(message)


if __name__ == '__main__':
    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 加载币安API配置
    bn_api_file = os.path.join(current_dir, 'bn.json')
    allert_all_file = os.path.join(current_dir, 'alert_all.json')
    autobn = AUTOBN.from_cfg(bn_api_file, allert_all_file,
                             '095984b1-5bc0-43ac-8037-d65a9608d120')
    app.run()
