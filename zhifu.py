import json
import os

import openai
import requests

openai.api_key = os.environ.get('openai')
msg = {
    "messages": [
        {
            "role": "system",
            "content": ""
        },
        {
            "role": "user",
            "content": "你好"
        },
    ],
    "stream": True,
    "model": "gpt-3.5-turbo",
    "temperature": 0.5,
    "presence_penalty": 0,
    "frequency_penalty": 0,
    "top_p": 1
}
res = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
        {
            "role": "system",
            "content": ""
        },
        {
            "role": "user",
            "content": "你好,写一篇50字的关于金钱的作文"
        },
    ], stream=True, presence_penalty=0, temperature=0.5, top_p=1
)
# collected_chunks = []
# collected_messages = []
# for chunk in res:  # calculate the time delay of the chunk
#     collected_chunks.append(chunk)  # save the event response
#     chunk_message = chunk['choices'][0]['delta']  # extract the message
#     if not chunk_message.get('content'):
#         collected_messages.append(chunk_message.get('content'))  # save the message
#     # print(f" seconds after request: {chunk_message.get('content')}")  # print the delay and text
# print(json.dumps(res))
def read_file(file_name, size):
    """分批读取文件"""
    with open(file_name, mode='rb') as fp:
        while True:
            c = fp.read(size)
            if c:
                # 生成器，相当于一个特殊的迭代器，当运行到这个语句的时候会保存当前的对象；下次再运行到这里的时候会接着上次的对象继续运行。
                yield c
            else:
                break
print(5,type(read_file),type(res))