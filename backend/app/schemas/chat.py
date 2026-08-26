# 聊天接口的数据模型
# 用 Pydantic 保证：请求字段必填、类型正确，非法输入直接被 422 拦截

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """用户发送一条消息的请求体"""

    message: str = Field(..., min_length=1, description="用户输入的消息内容")
    conversation_id: int | None = Field(
        None, description="会话 ID；首次对话留空，后端自动创建并返回新 ID"
    )


class ChatResponse(BaseModel):
    """非流式聊天的响应体"""

    reply: str = Field(..., description="玄枢的回复内容")
    model: str = Field(..., description="实际使用的模型名称")
    conversation_id: int = Field(..., description="本次对话所属会话 ID")
