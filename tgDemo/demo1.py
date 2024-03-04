import redis

# 消息生产者
r = redis.Redis(host='localhost', port=6379)
p = r.pubsub()
p.subscribe('tg')
