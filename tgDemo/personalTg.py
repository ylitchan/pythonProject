# @Date: 2024/3/6
# @Author: ylitchan
# @Source: rdti_crawl_defense
# @Site:
from datetime import datetime
import base64
import hashlib
import requests
from pyrogram import Client
import os

api_id = 23306769
api_hash = "c4edead58afb1bf4fe0c1da91e820730"
phone_number = "+8617880356481"
api_id = 23306769
api_hash = "c4edead58afb1bf4fe0c1da91e820730"
proxy = {
    "scheme": "http",  # "socks4", "socks5" and "http" are supported
    "hostname": "127.0.0.1",
    "port": 1081,
    # "username": "username",
    # "password": "password"
}
app = Client("my_account", api_id, api_hash, proxy=proxy)
session = requests.Session()
session.verify = False


# session.proxies = proxies = {'https': 'http://192.168.6.42:10502', 'http': 'http://192.168.6.42:10502'}


def path2base64(path: str) -> dict:
    """
    文件转换为base64
    :param path: 文件路径
    :return:
    """
    with open(path, "rb") as f:
        byte_data = f.read()
    base64_str = base64.b64encode(byte_data).decode("ascii")  # 二进制转base64
    return {"base64": base64_str, "md5": md5(byte_data)}


def path2md5(path: str) -> str:
    """
    文件转换为md5
    :param path: 文件路径
    :return:
    """
    with open(path, "rb") as f:
        byte_data = f.read()
    md5_str = md5(byte_data)
    return md5_str


def md5(text: all) -> str:
    """
    md5加密
    :param text:
    :return:
    """
    m = hashlib.md5()
    m.update(text)
    return m.hexdigest()


@app.on_message()
async def raw(client, message):
    username = message.from_user.username if message.from_user else ""
    title = message.chat.title if message.chat else ""
    if username in ['Keycoooo', 'USTDAO', 'ylitchan', 'EinsteinLee'] or title in ['一撇 Degen Calls',
                                                                                  'Daily alpha😊财富密码😊UST DAO投研']:
        username = message.from_user.first_name if message.from_user else ""
        print(datetime.now(), f'{title}\n{username}\n\n')
        reply = message.reply_to_message
        if reply and reply.photo:
            photo = await app.download_media(message=reply)
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=2caca472-4893-490d-aa1b-76e69f4e9b3c',
                headers={'Content-Type': 'application/json'}, json={
                    "msgtype": "image",
                    "image": path2base64(photo),
                })
            os.remove(photo)
        reply_caption = reply.caption if reply and reply.caption else ''
        reply_text = reply.text if reply and reply.text else ''
        if reply_text or reply_caption:
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=2caca472-4893-490d-aa1b-76e69f4e9b3c',
                headers={'Content-Type': 'application/json'}, json={
                    "msgtype": "text",
                    "text": {
                        'content': f'{title}\n{username}\n😊回复😊:\n{reply_text}{reply_caption}'}
                })

        if message.photo:
            photo = await app.download_media(message=message)
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=2caca472-4893-490d-aa1b-76e69f4e9b3c',
                headers={'Content-Type': 'application/json'}, json={
                    "msgtype": "image",
                    "image": path2base64(photo),
                })
            os.remove(photo)
        caption = message.caption or ''
        text = message.text or ''
        if text or caption:
            session.post(
                url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=2caca472-4893-490d-aa1b-76e69f4e9b3c',
                headers={'Content-Type': 'application/json'}, json={
                    "msgtype": "text",
                    "text": {
                        'content': f'{title}\n{username}\n😊说😊:\n{text}{caption}'}
                })
    # r.publish('tg',json.dumps([message.chat.title, message.text]))


messaage = ['__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__',
            '__getattribute__', '__getstate__', '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__',
            '__lt__', '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__',
            '__setstate__', '__sizeof__', '__str__', '__subclasshook__', '__weakref__', '_client', '_parse',
            'animation', 'audio', 'author_signature', 'bind', 'caption', 'caption_entities', 'channel_chat_created',
            'chat', 'click', 'command', 'contact', 'continue_propagation', 'copy', 'date', 'default', 'delete',
            'delete_chat_photo', 'dice', 'document', 'download', 'edit', 'edit_caption', 'edit_date', 'edit_media',
            'edit_reply_markup', 'edit_text', 'empty', 'entities', 'forward', 'forward_date', 'forward_from',
            'forward_from_chat', 'forward_from_message_id', 'forward_sender_name', 'forward_signature', 'forwards',
            'from_scheduled', 'from_user', 'game', 'game_high_score', 'get_media_group', 'group_chat_created',
            'has_media_spoiler', 'has_protected_content', 'id', 'left_chat_member', 'link', 'location', 'matches',
            'media', 'media_group_id', 'mentioned', 'migrate_from_chat_id', 'migrate_to_chat_id', 'new_chat_members',
            'new_chat_photo', 'new_chat_title', 'outgoing', 'photo', 'pin', 'pinned_message', 'poll', 'react',
            'reactions', 'reply', 'reply_animation', 'reply_audio', 'reply_cached_media', 'reply_chat_action',
            'reply_contact', 'reply_document', 'reply_game', 'reply_inline_bot_result', 'reply_location',
            'reply_markup', 'reply_media_group', 'reply_photo', 'reply_poll', 'reply_sticker', 'reply_text',
            'reply_to_message', 'reply_to_message_id', 'reply_to_top_message_id', 'reply_venue', 'reply_video',
            'reply_video_note', 'reply_voice', 'retract_vote', 'scheduled', 'sender_chat', 'service', 'sticker',
            'stop_propagation', 'supergroup_chat_created', 'text', 'unpin', 'venue', 'via_bot', 'video',
            'video_chat_ended', 'video_chat_members_invited', 'video_chat_scheduled', 'video_chat_started',
            'video_note', 'views', 'voice', 'vote', 'web_app_data', 'web_page']
user = ['__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__',
        '__getattribute__', '__getstate__', '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__', '__lt__',
        '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__setstate__',
        '__sizeof__', '__str__', '__subclasshook__', '__weakref__', '_client', '_parse', '_parse_status',
        '_parse_user_status', 'archive', 'bind', 'block', 'continue_propagation', 'dc_id', 'default', 'emoji_status',
        'first_name', 'get_common_chats', 'id', 'is_bot', 'is_contact', 'is_deleted', 'is_fake', 'is_mutual_contact',
        'is_premium', 'is_restricted', 'is_scam', 'is_self', 'is_support', 'is_verified', 'language_code', 'last_name',
        'last_online_date', 'mention', 'next_offline_date', 'phone_number', 'photo', 'restrictions', 'status',
        'stop_propagation', 'unarchive', 'unblock', 'username']
chat = ['__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__',
        '__getattribute__', '__getstate__', '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__', '__lt__',
        '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__setstate__',
        '__sizeof__', '__str__', '__subclasshook__', '__weakref__', '_client', '_parse', '_parse_channel_chat',
        '_parse_chat', '_parse_chat_chat', '_parse_dialog', '_parse_full', '_parse_user_chat', 'add_members', 'archive',
        'available_reactions', 'ban_member', 'bind', 'bio', 'can_set_sticker_set', 'dc_id', 'default', 'description',
        'distance', 'export_invite_link', 'first_name', 'get_member', 'get_members', 'has_protected_content', 'id',
        'invite_link', 'is_creator', 'is_fake', 'is_restricted', 'is_scam', 'is_support', 'is_verified', 'join',
        'last_name', 'leave', 'linked_chat', 'mark_unread', 'members_count', 'permissions', 'photo', 'pinned_message',
        'promote_member', 'restrict_member', 'restrictions', 'send_as_chat', 'set_description', 'set_photo',
        'set_protected_content', 'set_title', 'sticker_set_name', 'title', 'type', 'unarchive', 'unban_member',
        'unpin_all_messages', 'username']

app.run()
