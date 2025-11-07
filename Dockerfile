# 使用Python 3.9作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有文件到容器
COPY . .

# 创建日志目录
RUN mkdir -p logs

# 暴露端口
EXPOSE 5000

# 默认命令
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--limit-request-line", "16380", "app:app"]
