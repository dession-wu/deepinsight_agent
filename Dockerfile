FROM python:3.10-slim-bookworm

# 替换 Debian 源为阿里云镜像（加速 apt）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null \
    || sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list

WORKDIR /app

# 先安装依赖（利用镜像层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    -r requirements.txt

# 拷贝业务代码
COPY . .

# 容器内以非 root 运行
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8085

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8085"]