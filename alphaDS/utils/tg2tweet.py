from fastapi import FastAPI, Body
import uvicorn
from utils.tools import *

# 创建生产者实例
producer = KafkaProducer(bootstrap_servers=['localhost:9092'])
today = ['']
app = FastAPI()


@app.post("/")
async def root(json=Body(None)):
    pass


@app.post("/ishtar")
async def ishtar(json=Body(None)):
    text = ''
    for i in parse('$..text').find(json):
        text += i.value
    print('这是获取的文本', text)
    member = re.findall(r'@.*?\n', text)
    for i in member:
        try:
            user_id = client_tweet.get_user(username=i.replace('\n', '').replace('@', '')).data.id
            print(user_id)
            producer.send('alpha', str(user_id).encode('utf-8'))
        except:
            continue

    # return {"challenge": json["challenge"]}


uvicorn.run(app, host='127.0.0.1', port=8000)
