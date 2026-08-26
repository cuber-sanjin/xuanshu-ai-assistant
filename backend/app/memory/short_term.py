# 短期记忆：会话历史的存取
# 为什么"短期记忆 = 数据库存历史 + 每次请求手动拼装"（方案 A）而不是 LangGraph checkpointer？
#   - 学习项目：自己管理历史更直观，能清楚看到每条消息的来龙去脉
#   - 面试点：短期记忆的两种实现——框架内置（checkpointer）vs 业务层自管（本方案）。
#     自管方案对企业更常见：历史要同时服务"对话上下文"和"前端展示/审计"，单一来源。
#
# 窗口控制：只取最近 N 条消息喂给 LLM（token 预算有限，无限历史会超上下文窗口）。
# 真实企业会用 token 计数精确裁剪（如 tiktoken），MVP 先用条数近似。

import logging

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy.orm import Session

from app.database.models import Conversation, Message

logger = logging.getLogger(__name__)

# 喂给 LLM 的最大历史消息条数（约 10 轮对话）
MAX_HISTORY_MESSAGES = 20

# 默认会话标题（MVP 不做自动摘要）
DEFAULT_CONVERSATION_TITLE = "新对话"


def get_or_create_conversation(db: Session, conversation_id: int | None) -> Conversation:
    """获取已有会话，或创建新会话。

    conversation_id 为空 → 创建（前端首次对话）；
    非空 → 校验存在，否则抛 ValueError（由 API 层转 404）。
    """
    if conversation_id is None:
        conv = Conversation(user_id=1, title=DEFAULT_CONVERSATION_TITLE)
        db.add(conv)
        db.commit()
        db.refresh(conv)
        logger.info("new conversation created id=%d", conv.id)
        return conv

    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise ValueError(f"会话 {conversation_id} 不存在")
    return conv


def load_history(db: Session, conversation_id: int) -> list[BaseMessage]:
    """加载最近 N 条历史消息，转换为 LangChain 消息对象。

    只保留 user/assistant 文本（工具调用过程不持久化——
    工具结果已由助手总结进回复，无需重放）。
    按 id 升序返回（时间正序）。
    """
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(MAX_HISTORY_MESSAGES)
        .all()
    )
    rows.reverse()  # 时间正序

    history: list[BaseMessage] = []
    for m in rows:
        if m.role == "user":
            history.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            history.append(AIMessage(content=m.content))
        # 其他 role 忽略（防御性）
    return history


def save_message(db: Session, conversation_id: int, role: str, content: str) -> None:
    """保存一条消息（user 或 assistant）。"""
    msg = Message(conversation_id=conversation_id, role=role, content=content)
    db.add(msg)
    db.commit()


def maybe_set_title(db: Session, conversation_id: int, first_user_message: str) -> None:
    """若会话还是默认标题，用第一条用户消息前 20 字自动命名。

    调用时机：保存用户消息之后（此时若会话为空，本条即第一条）。
    """
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.title != DEFAULT_CONVERSATION_TITLE:
        return
    title = first_user_message.strip()[:20] or DEFAULT_CONVERSATION_TITLE
    conv.title = title
    db.commit()
    logger.info("conversation %d auto-titled: %s", conversation_id, title)
