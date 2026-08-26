# 图的节点（Nodes）：LangGraph 中每个节点是一段"单一职责"的处理逻辑
# Phase 6 节点清单：
#   load_memory  对话前：加载长期记忆写入 state（agent 会拼进 system prompt）
#   agent        核心推理：绑定工具，可输出 tool_calls 或最终回答
#   save_memory  对话后：提取器判断是否产生值得长期记住的信息，落库
#
# 面试点：节点只负责"读 state → 干活 → 返回 state 更新片段"，
# 图编排（谁先谁后、是否循环）完全由 graph.py 控制，两者解耦。

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from starlette.concurrency import run_in_threadpool

from app.agent.prompts import build_system_prompt
from app.agent.state import AgentState
from app.database.database import SessionLocal
from app.memory.extractor import extract_memories
from app.memory.long_term import (
    DEFAULT_USER_ID,
    MAX_INJECT_MEMORIES,
    format_memories_for_prompt,
    save_memories,
)
from app.rag.hybrid import get_relevant_memories
from app.services.llm import get_chat_llm
from app.tools import ALL_TOOLS

logger = logging.getLogger(__name__)

# 绑定工具的 LLM（进程内单例）
# bind_tools 作用：把工具 schema 注入模型 API，让模型知道"有哪些工具可用、怎么传参"，
# 模型据此输出结构化的 tool_calls（工具名 + 参数 JSON），而不是直接执行
_bound_llm: ChatOpenAI | None = None


def _get_bound_llm() -> ChatOpenAI:
    global _bound_llm
    if _bound_llm is None:
        _bound_llm = get_chat_llm().bind_tools(ALL_TOOLS)
        logger.info("LLM 已绑定 %d 个工具", len(ALL_TOOLS))
    return _bound_llm


async def load_memory_node(state: AgentState) -> dict:
    """对话前节点：加载与当前问题最相关的长期记忆，注入 state["memories"]。

    Phase R 起：取最后一条 HumanMessage 作为查询语句做语义召回
    （向量 + RRF → importance 兜底）；开关关闭时与旧行为一致。
    agent 节点会把 memories 拼进 system prompt，让玄枢"带着对用户的了解"回答。
    失败降级：记忆加载失败不阻断对话（返回空列表）。
    """
    try:
        # 查询语句：本轮用户问题（语义召回相关性的锚点）
        query_text = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                query_text = msg.content
                break

        with SessionLocal() as db:
            memories = await run_in_threadpool(
                get_relevant_memories,
                db,
                DEFAULT_USER_ID,
                MAX_INJECT_MEMORIES,
                query_text,
            )
        prompt_text = format_memories_for_prompt(memories)
        logger.info("load_memory: injected %d memories", len(memories))
        return {"memories": [prompt_text] if prompt_text else []}
    except Exception as e:
        logger.warning("load_memory failed, continue without memory: %s", e)
        return {"memories": []}


async def agent_node(state: AgentState) -> dict:
    """核心对话节点：system 人设 + 长期记忆 + 历史消息 → 绑定工具的 LLM。

    两种返回形态：
    1. 需要工具：AIMessage.tool_calls 非空 → 条件边路由到 tools 节点
    2. 直接回答：AIMessage.tool_calls 为空 → 条件边走向 save_memory / END
    """
    llm = _get_bound_llm()

    # 组装 system 提示词：人设 + 日期 + 长期记忆上下文
    memory_context = state.get("memories") or []
    system_prompt = build_system_prompt(memory_context)

    messages = [SystemMessage(content=system_prompt), *state["messages"]]
    response = await llm.ainvoke(messages)

    tool_calls = getattr(response, "tool_calls", None) or []
    logger.info(
        "agent_node: msgs=%d tool_calls=%d",
        len(messages),
        len(tool_calls),
    )
    return {"messages": [response]}


async def save_memory_node(state: AgentState) -> dict:
    """对话后节点：判断本轮是否产生值得长期记住的信息，落库。

    流程：
    1. 取本轮用户消息（最后一个 HumanMessage）与最终回复（最后一个 AIMessage 的正文）
    2. 提取器（快速模型 + 结构化输出）判断 should_save + items
    3. 值得保存 → 写入 memories 表（long_term.save_memories 自带内容去重）

    设计取舍：
    - 提取放在图内：单次调用闭环、逻辑内聚（代价：done 事件前多 1~3s，不影响已输出的文字）
    - 提取失败/超时降级为不保存，绝不阻断主流程
    """
    try:
        # 找到本轮的用户消息和最终 AI 回复
        user_text = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage) and msg.content:
                user_text = msg.content if isinstance(msg.content, str) else str(msg.content)
                break

        reply_text = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                reply_text = msg.content if isinstance(msg.content, str) else str(msg.content)
                break

        if not user_text or not reply_text:
            return {"messages": []}

        # 提取（内部已兜底：失败返回 should_save=False）
        extraction = await extract_memories(user_text, reply_text)

        if extraction.should_save and extraction.items:
            items = [
                (item.memory_type, item.content, item.importance)
                for item in extraction.items
            ]
            with SessionLocal() as db:
                ids = await run_in_threadpool(
                    save_memories, db, DEFAULT_USER_ID, items
                )
            logger.info("save_memory: wrote %d memories %s", len(ids), ids)
    except Exception as e:
        # 记忆保存失败绝不能影响对话主流程
        logger.warning("save_memory failed, skip: %s", e)

    return {"messages": []}
