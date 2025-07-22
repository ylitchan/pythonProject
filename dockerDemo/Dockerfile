# 使用官方 Python 镜像作为基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 拷贝项目文件到镜像中
COPY . /app

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置启动命令
CMD ["python", "autoBN.py"]
#%%
