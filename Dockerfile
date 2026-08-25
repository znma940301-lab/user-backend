# 使用 Python 官方镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有代码
COPY . .

# 暴露端口（CloudBase 云托管默认用 8080）
EXPOSE 8080

# 启动命令（用 gunicorn 运行 Flask）
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "app:app"]