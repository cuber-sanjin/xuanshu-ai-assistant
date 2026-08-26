# 记忆提取器：判断本轮对话是否产生值得长期记住的信息（Phase 6 核心）
#
# 为什么需要"提取"而不是"全部保存"？
#   - 噪音问题："今天天气不错"这类寒暄没有长期价值，全存会让记忆库变垃圾场
#   - 成本问题：每条都存，召回时上下文爆炸
#   - 这就是"信息过滤"——真实 Agent 记忆系统必备环节
#
# 实现：专用提取模型 + 结构化输出（with_structured_output）
#   1. 把"用户消息 + 助手回复"交给提取模型
#   2. 模型必须输出 MemoryExtraction 结构（should_save + items[]）
#   3. Python 根据结果决定是否写入 SQLite
# 模型"判断"、Python "落库"，职责分离。

import logging
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.services.llm import get_extractor_llm

logger = logging.getLogger(__name__)

# 记忆类型（与 long_term.MEMORY_TYPES 保持一致）
MemoryType = Literal[
    "preference",  # 偏好：用户喜欢什么
    "profile",  # 资料：名字、身份、背景
    "goal",  # 目标：正在追求什么
    "learning",  # 学习：正在学什么
    "habit",  # 习惯：行为模式
    "important_event",  # 重要事件
]


class MemoryItem(BaseModel):
    """一条待保存的记忆"""

    memory_type: MemoryType
    content: str = Field(..., min_length=1, description="记忆内容（简洁、客观、一句话）")
    importance: float = Field(0.5, ge=0.0, le=1.0, description="重要性 0~1")


class MemoryExtraction(BaseModel):
    """提取结果：是否保存 + 保存哪些"""

    should_save: bool = Field(..., description="本轮对话是否有值得长期记住的信息")
    items: list[MemoryItem] = Field(default_factory=list, description="要保存的记忆列表")


# 提取任务提示词：明确什么值得记、什么不值得记
EXTRACTOR_PROMPT = """你是记忆提取助手。根据一段对话，判断是否有值得长期记住的"用户信息"。

值得记住的（should_save=true）：
- 用户的个人信息：名字、职业、所在地、身份（profile）
- 用户的目标/正在准备的事：如"正在准备 Python Agent 开发岗位面试"（goal）
- 用户的学习内容/技术方向（learning）
- 用户明确说"记住…"的内容（preference / important_event）
- 稳定的偏好或习惯："我喜欢晚上学习"（preference / habit）

不值得记住的（should_save=false）：
- 寒暄、天气、一次性提问
- 对话中的临时内容（"帮我算一下"）
- 没有用户个人属性的泛泛话题

要求：
- content 用第三人称概括（如"用户正在准备Python Agent开发岗位面试"）
- 每条记忆独立成条，不要合并多条无关信息
- importance：明确的目标/身份给 0.8+，一般偏好给 0.5-0.7，模糊信息 0.3-0.5"""


async def extract_memories(user_message: str, assistant_reply: str) -> MemoryExtraction:
    """从一轮对话中提取值得长期记住的信息。

    输入：用户消息 + 助手回复（同一轮）
    输出：MemoryExtraction（Pydantic 模型，已结构化）
    """
    llm = get_extractor_llm().with_structured_output(MemoryExtraction)

    messages = [
        SystemMessage(content=EXTRACTOR_PROMPT),
        HumanMessage(content=user_message),
        AIMessage(content=assistant_reply),
    ]

    try:
        result = await llm.ainvoke(messages)
        logger.info(
            "memory extract: should_save=%s items=%d",
            result.should_save,
            len(result.items),
        )
        return result
    except Exception as e:
        # 提取失败不能影响主流程：降级为"不保存"
        logger.warning("memory extract failed, skip: %s", e)
        return MemoryExtraction(should_save=False, items=[])
