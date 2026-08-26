# Note 接口数据模型

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NoteCreate(BaseModel):
    """创建笔记的请求体"""

    content: str = Field(..., min_length=1, description="笔记内容")


class NoteOut(BaseModel):
    """笔记响应体"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    created_at: datetime
