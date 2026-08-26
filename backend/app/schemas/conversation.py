# 会话列表接口数据模型

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageOut(BaseModel):
    """会话中的一条消息"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str  # user / assistant
    content: str
    created_at: datetime


class ConversationOut(BaseModel):
    """会话列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    message_count: int  # 消息条数
    last_message: str | None  # 最后一条消息预览
