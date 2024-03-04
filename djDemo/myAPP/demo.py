# encoding=utf-8
# 随机数，随机读取每一行的数据
import linecache
import random
from iFinDPy import *


# a = random.randrange(1, 9433)  # 1-9中生成随机数
# print(a)
# # 从文件poem.txt中对读取第a行的数据
# theline = linecache.getline(r'picture.txt',random.randrange(1, 9433))
# print(theline)
# with open('picture.txt','r+') as f:
#     # print(f.readlines())
#     for i in f.readlines():
#         with open('closeup.txt',"a+") as p:
#             p.write(i[38:-2].replace('\\','/')+'\n')
#         #print(i[54:-2])
# thsLogin = THS_iFinDLogin("zsdx325", "916530")
# indicators = THS_RQ('300033.SZ', 'changeRatio,latest,upperLimit').data
# print(indicators['thscode'])
print(datetime.today().strftime("%H:%M")=='20:34')

#print([r'/static/closeup/'+linecache.getline(r'picture.txt',random.randrange(1, 9434))[54:-2] for i in range(10)])