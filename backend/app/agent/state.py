# Agent State 定义：LangGraph 图中流动的数据结构
# 为什么用 TypedDict + Annotated？
#   - TypedDict: 声明"图的状态长什么样"，让每个节点知道能读写哪些字段
#   - Annotated[list, add_messages]: add_messages 是"消息合并器(reducer)"，
#     新消息追加到列表而不是覆盖，保证多轮/多节点消息不会互相冲掉
# 面试点：LangGraph State 就是节点的"共享黑板"——每个节点读旧状态、返回更新片段，
# 由 reducer 决定如何合并。这是理解 Agent 状态管理的核心概念。

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """玄枢 Agent 的图状态。

    字段说明：
    - messages: 消息序列（Human/AI/System/Tool），add_messages 自动追加
    - memories : 长期记忆注入（Phase 6，load_memory 节点写入，agent 节点读入上下文）
    - user_id : 预留（多用户时区分记忆/会话归属，MVP 固定为 1）
    """

    messages: Annotated[list, add_messages]
    # 长期记忆文本列表（已格式化成可读字符串，直接拼进 system prompt）
    memories: list[str]
