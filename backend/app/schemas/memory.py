# Memory 接口数据模型

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MemoryOut(BaseModel):
    """记忆响应体"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    memory_type: str
    content: str
    importance: float
    created_at: datetime
    updated_at: datetime
