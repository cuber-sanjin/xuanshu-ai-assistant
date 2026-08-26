# 聊天路由
# Phase 5 起两个接口都带会话历史：
#   POST /api/chat          非流式（Swagger 调试/兜底）
#   POST /api/chat/stream   SSE 流式（前端主用，逐字显示）
#
# 会话流程（短期记忆）：
#   1. 获取或创建 Conversation（conversation_id 为空则新建）
#   2. 加载最近 N 条历史消息（memory/short_term.load_history）
#   3. 保存本次用户消息
#   4. graph 带历史执行（历史 + 新消息一起喂给 LLM）
#   5. 流结束后保存助手回复
# 注意：async 端点内不能直接调同步 SQLAlchemy（会阻塞事件循环），
# 所有 DB 操作用 run_in_threadpool 包裹。

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from starlette.concurrency import run_in_threadpool

from app.agent.graph import get_agent
from app.config import settings
from app.database.database import SessionLocal
from app.memory.short_term import (
    get_or_create_conversation,
    load_history,
    maybe_set_title,
    save_message,
)
from app.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

# 路由前缀 /api/chat，统一挂在 main.py
router = APIRouter(prefix="/api/chat", tags=["chat"])


def _sse(event: dict) -> str:
    """把事件 dict 序列化为 SSE 帧。

    SSE 帧格式：data: <json>\n\n
    ensure_ascii=False 保证中文以 UTF-8 明文传输（否则变 \\uXXXX，前端仍能解析但体积大）
    """
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("", response_model=ChatResponse, summary="发送一条消息，获取玄枢回复（非流式）")
async def chat(req: ChatRequest) -> ChatResponse:
    """非流式聊天（带会话历史）。"""
    try:
        graph = get_agent()

        # --- 1. 会话与历史（同步 DB，线程池包裹） ---
        with SessionLocal() as db:
            conv = await run_in_threadpool(get_or_create_conversation, db, req.conversation_id)
            # 关键：立刻捕获会话 ID（int）。SQLAlchemy 的 commit() 会过期 ORM 实例，
            # 之后在 with 块外访问 conv.id 会触发"刷新"，而会话已关闭 → 报错
            conv_id = conv.id
            history = await run_in_threadpool(load_history, db, conv_id)
            # 先存用户消息，再带历史执行（历史不含本条）
            await run_in_threadpool(save_message, db, conv_id, "user", req.message)
            # 新会话首条消息自动命名（标题便于会话列表展示）
            await run_in_threadpool(maybe_set_title, db, conv_id, req.message)

            # --- 2. 带历史调用图 ---
            result = await graph.ainvoke(
                {"messages": [*history, HumanMessage(content=req.message)]}
            )
            last_msg = result["messages"][-1]
            reply = last_msg.content if isinstance(last_msg.content, str) else str(last_msg.content)

            # --- 3. 保存助手回复 ---
            await run_in_threadpool(save_message, db, conv_id, "assistant", reply)

        logger.info("chat conv=%d history=%d reply_len=%d", conv_id, len(history), len(reply))
        return ChatResponse(reply=reply, model=settings.llm_model, conversation_id=conv_id)
    except ValueError as e:
        # 会话不存在
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail=f"玄枢暂时无法回答：{e}") from e


@router.post("/stream", summary="发送一条消息，SSE 流式获取玄枢回复")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """SSE 流式聊天（带会话历史）。

    事件协议（见 docs/architecture.md 第三节）：
      {"type": "token", "content": "..."}    逐字输出
      {"type": "tool_start", "tool": "...", "args": {...}}  工具开始（前端显示状态条）
      {"type": "tool_end", "tool": "...", "result": "..."}  工具结束
      {"type": "done", "conversation_id": 3}   流结束（带回会话 ID）
      {"type": "error", "message": "..."}     出错
    """
    graph = get_agent()

    async def event_generator():
        # 会话相关变量在生成器内部获取（请求校验失败时也能发 error 事件）
        conv_id = None
        try:
            # 初始帧：告诉客户端重连策略（SSE 规范字段）
            yield "retry: 3000\n\n"

            # --- 1. 会话与历史 ---
            with SessionLocal() as db:
                conv = await run_in_threadpool(
                    get_or_create_conversation, db, req.conversation_id
                )
                conv_id = conv.id
                history = await run_in_threadpool(load_history, db, conv_id)
                await run_in_threadpool(save_message, db, conv_id, "user", req.message)
                await run_in_threadpool(maybe_set_title, db, conv_id, req.message)

            # --- 2. 流式执行图 ---
            reply_parts: list[str] = []
            async for event in graph.astream_events(
                {"messages": [*history, HumanMessage(content=req.message)]},
                version="v2",
            ):
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    # 关键过滤：图内可能有多个模型（agent 主模型 + save_memory 的提取模型），
                    # 只转发 agent 节点的输出增量；提取模型的 JSON 输出绝不能给用户看到
                    node = event.get("metadata", {}).get("langgraph_node")
                    if node is not None and node != "agent":
                        continue

                    chunk = event["data"]["chunk"]
                    # 跳过工具调用的参数增量（工具调用不是正文）
                    if getattr(chunk, "tool_call_chunks", None):
                        continue
                    content = chunk.content
                    if not content:
                        continue
                    # content 可能是 str 或 [{"type":"text","text":"..."}] 列表
                    if isinstance(content, str):
                        text = content
                    else:
                        text = "".join(
                            b.get("text", "") for b in content if isinstance(b, dict)
                        )
                    if text:
                        reply_parts.append(text)
                        yield _sse({"type": "token", "content": text})

                elif kind == "on_tool_start":
                    # 工具开始执行：通知前端显示"正在调用 XX"
                    # 注意：工具名在 event["name"]（runnable 名），不在 data 里
                    name = event.get("name", "unknown")
                    args = event["data"].get("input", {})
                    yield _sse({"type": "tool_start", "tool": name, "args": args})

                elif kind == "on_tool_end":
                    # 工具执行完成：把结果摘要带给前端
                    name = event.get("name", "unknown")
                    output = event["data"].get("output", "")
                    result = str(output)[:200]  # 截断，避免大结果刷屏
                    yield _sse({"type": "tool_end", "tool": name, "result": result})

            # --- 3. 保存助手回复 + done 事件带回会话 ID ---
            reply = "".join(reply_parts)
            with SessionLocal() as db:
                await run_in_threadpool(save_message, db, conv_id, "assistant", reply)

            yield _sse({"type": "done", "conversation_id": conv_id})

        except Exception as e:
            logger.exception("chat stream failed")
            yield _sse({"type": "error", "message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # 关键：让 nginx 等反向代理不缓冲 SSE（否则逐字效果变整块输出）
            "X-Accel-Buffering": "no",
        },
    )
