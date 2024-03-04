import json

import requests
# from demo1 import *
from pyrogram import Client
from jsonpath_ng import parse, parser

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
session = requests.session()

@app.on_message()
async def raw(client, message):
    if 'USTDAO' == message.from_user.username:
        print(message.chat.title, message.from_user.username, message.text, sep='\n')
        session.post(
            url='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=2caca472-4893-490d-aa1b-76e69f4e9b3c',
            headers={'Content-Type': 'application/json'}, json={
                "msgtype": "text",
                "text": {'content': f'{message.chat.title}\n{message.from_user.username}:\n{message.reply_to_message.text}\n{message.text}'}
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
