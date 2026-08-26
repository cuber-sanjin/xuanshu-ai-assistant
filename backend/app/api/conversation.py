# 会话管理 REST API：会话列表 / 历史消息 / 删除
# 供前端会话列表（ConversationList.vue）切换与管理多轮对话

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Conversation, Message
from app.memory.long_term import DEFAULT_USER_ID
from app.schemas.conversation import ConversationOut, MessageOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversation"])


@router.get("", response_model=list[ConversationOut], summary="会话列表（倒序）")
def list_conversations(db: Session = Depends(get_db)):
    """列出全部会话：标题 + 消息数 + 最后消息预览。

    注：每个会话两次查询（计数 + 末条）→ 简单场景够用，
    大数据量时应改为聚合查询（GROUP BY + JOIN 一次取回）。
    """
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == DEFAULT_USER_ID)
        .order_by(Conversation.created_at.desc())
        .all()
    )

    result = []
    for c in convs:
        count = (
            db.query(Message).filter(Message.conversation_id == c.id).count()
        )
        last = (
            db.query(Message)
            .filter(Message.conversation_id == c.id)
            .order_by(Message.id.desc())
            .first()
        )
        result.append(
            ConversationOut(
                id=c.id,
                title=c.title,
                created_at=c.created_at,
                message_count=count,
                last_message=last.content[:80] if last else None,
            )
        )
    return result


@router.get("/{conversation_id}/messages", response_model=list[MessageOut], summary="某会话的历史消息")
def get_messages(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail=f"会话 {conversation_id} 不存在")

    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id)  # 时间正序
        .all()
    )


@router.delete("/{conversation_id}", status_code=204, summary="删除会话（含消息）")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail=f"会话 {conversation_id} 不存在")

    # 会话与消息配置了 cascade="all, delete-orphan"，删会话即删消息
    db.delete(conv)
    db.commit()
    logger.info("conversation %d deleted", conversation_id)
