import datetime
import schedule
from utils.tools import *

m = set()
alpha = CallerInfo.objects.filter(list_account='dao_ust').values('tweet_user')
for i in alpha:
    m.add(i['tweet_user'])
with open('callers.txt', 'w') as f:
    json.dump(list(m), f)
