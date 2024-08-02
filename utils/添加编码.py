import os
d=r'D:\pythonProject\utils\zzzb'
a=[]
for root,dirs,files in os.walk(d):
    print(root)
    for file in files:
        if file.endswith('.html'):
            with open(os.path.join(root,file), 'r',encoding='utf-8') as f:
                content = f.read()
            content = '<meta content="text/html; charset=utf-8" http-equiv="Content-Type">\n' + content
            with open(os.path.join(root,file), 'w',encoding='utf-8') as f:
                f.write(content)
print(len(a))