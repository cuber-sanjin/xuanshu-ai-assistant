# 语音接口数据模型

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """语音合成请求体"""

    text: str = Field(..., min_length=1, max_length=500, description="要朗读的文本（≤500字）")
    voice: str | None = Field(None, description="音色：Cherry/Serena/Ethan，空用默认")
