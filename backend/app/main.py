# 玄枢后端入口
# 职责：
#   1. 创建 FastAPI 应用实例
#   2. 注册所有路由
#   3. 配置 CORS（开发期前端走 Vite proxy 时其实用不到，但保留以便直连调试）
#   4. 启动日志

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, conversation, memory, note, todo, voice
from app.database.database import init_db

# 统一日志格式：时间 | 级别 | 模块 | 消息
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期钩子：启动时初始化数据库表与种子数据"""
    init_db()
    logging.info("数据库初始化完成")
    logging.info("玄枢后端启动完成")
    yield
    logging.info("玄枢后端已关闭")


app = FastAPI(
    title="玄枢 · 个人智能生活助手",
    description="基于 FastAPI + LangChain + LangGraph + 阿里云百炼 的个人 AI Agent。"
    "Swagger 文档即调试工具：直接在此页测试所有接口。",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS：允许浏览器跨域直连（开发期若不用 Vite proxy 可开启）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router)
app.include_router(conversation.router)
app.include_router(todo.router)
app.include_router(note.router)
app.include_router(memory.router)
app.include_router(voice.router)


@app.get("/health", tags=["system"], summary="健康检查")
async def health() -> dict:
    """存活探针：Docker/K8s 探活、前端启动检测都用它"""
    return {"status": "ok", "service": "xuan-shu-backend"}


# 直接运行时：python -m app.main
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
