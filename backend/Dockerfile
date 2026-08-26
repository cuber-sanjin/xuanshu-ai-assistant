# ===== 玄枢后端镜像 =====
# 生产镜像：python:3.13-slim（比 full 小 ~300MB，够跑 FastAPI + SQLite）
# 要点：
#   - 分层缓存：先 COPY requirements 再装依赖（改代码不重装 pip 包）
#   - 不 COPY .env：密钥通过 docker-compose environment 注入（镜像不留密）
#   - 单进程 uvicorn：SQLite + 单用户场景够用，避免多 worker 抢写

FROM python:3.13-slim

WORKDIR /app

# 先拷贝依赖清单并安装（利用 Docker 层缓存：依赖不变时重建秒级）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再拷贝应用代码
COPY app ./app

# Python 日志/输出立即刷盘（容器里不缓冲，SSE 逐字才及时）
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# 数据目录：docker-compose 挂持久卷到此，并通过 XUANSHU_DB_PATH 指向
RUN mkdir -p /app/data

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
