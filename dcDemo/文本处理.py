import json
msgs=[]
with open('msg.txt', 'r+', encoding='utf-8') as fp:
    for i in [line.strip('\n') for line in fp.readlines()]:
        if i not in msgs:
            msgs.append(i)
print(msgs,len(msgs))

fp0= open('msg0.txt', 'a+', encoding='utf-8')
fp1= open('msg1.txt', 'a+', encoding='utf-8')
fp2= open('msg2.txt', 'a+', encoding='utf-8')
while 1:
    fp0.write(msgs.pop()+'\n')
    fp1.write(msgs.pop()+'\n')
    fp2.write(msgs.pop()+'\n')