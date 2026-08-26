# Todo 接口数据模型

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TodoCreate(BaseModel):
    """创建待办的请求体"""

    title: str = Field(..., min_length=1, max_length=200, description="待办内容")
    due_time: str | None = Field(None, description="截止时间，如 '2026-08-23 15:00'")


class TodoUpdate(BaseModel):
    """更新待办的请求体（MVP 仅支持完成状态切换）"""

    completed: bool = Field(..., description="是否已完成")


class TodoOut(BaseModel):
    """待办响应体"""

    model_config = ConfigDict(from_attributes=True)  # 允许直接从 ORM 对象构造

    id: int
    title: str
    due_time: str | None
    completed: bool
    created_at: datetime
