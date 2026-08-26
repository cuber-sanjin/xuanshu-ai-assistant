# ORM 模型定义：数据库表结构
# Phase 4 只有 User / Todo / Note 三张表
# Phase 5 追加 Conversation / Message；Phase 6 追加 Memory
# Phase R（RAG）追加 Embedding：笔记/记忆的向量索引（JSON 文本列 + 纯 Python 余弦）
#
# 关系：User 1 ── N {Todo, Note}（MVP 固定 user_id=1 单用户）

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # 关系：一个用户有多条待办和笔记（ORM 反查用，MVP 暂不深度使用）
    todos: Mapped[list["Todo"]] = relationship(back_populates="user")
    notes: Mapped[list["Note"]] = relationship(back_populates="user")


class Todo(Base):
    """待办事项表"""

    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    due_time: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 可选截止时间
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped[User] = relationship(back_populates="todos")


class Note(Base):
    """笔记表"""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped[User] = relationship(back_populates="notes")


class Conversation(Base):
    """会话表：一次连续对话（Phase 5 短期记忆的容器）"""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), default="新对话")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """消息表：会话中的每条消息（role: user/assistant）"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Memory(Base):
    """长期记忆表：用户画像/偏好/目标等值得跨会话记住的信息（Phase 6）"""

    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # 记忆类型：preference / profile / goal / learning / habit / important_event
    memory_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 重要性 0~1，越高越优先被召回注入
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # onupdate：每次修改自动刷新（MVP 暂无编辑操作，保留字段）
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class Embedding(Base):
    """向量索引表（Phase R 向量检索 RAG）。

    为笔记/记忆条目保存嵌入向量，支持按用户隔离的语义检索。
    向量以 JSON 数组文本存储（个人数据量级下纯 Python 余弦足够，零额外依赖）。
    同一实体（entity_type + entity_id）只保留一条向量（UPSERT 覆盖）。
    """

    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'note' | 'memory'
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # 嵌入向量：JSON 数组字符串（如 "[0.01, -0.02, ...]"，1024 维）
    vector: Mapped[str] = mapped_column(Text, nullable=False)

    # 一个实体最多一条向量：upsert 依赖此约束（ON CONFLICT DO UPDATE）
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_embedding_entity"),
    )
