import json

from demo1 import *
for m in p.listen():
    try:
        print(json.loads(m.get('data')))
    except:
        continue
print(66666666666)