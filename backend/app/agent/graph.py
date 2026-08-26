# LangGraph 图组装：定义节点拓扑、条件边与执行顺序
# Phase 6 图结构（完整版）：
#
#   START → load_memory → agent ──(tool_calls?)──→ tools → agent ──(再判断)──→ …
#                 │                └──(无工具)──→ save_memory → END
#                 └────────────────────────────────────────────────────────────→ …（循环）
#
# 完整对话流程：
#   1. load_memory：加载长期记忆（对用户的了解）
#   2. agent：带着记忆 + 历史推理，决定调工具还是直接回答
#   3. tools：执行工具 → 回 agent（ReAct 循环）
#   4. save_memory：提取本轮是否产生新记忆 → 落库
#   5. END
#
# 循环次数由 LangGraph 内置 recursion_limit 限制（默认 25），防止死循环。

import logging
from functools import lru_cache
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.nodes import agent_node, load_memory_node, save_memory_node
from app.agent.state import AgentState
from app.tools import ALL_TOOLS

logger = logging.getLogger(__name__)


def should_continue(state: AgentState) -> Literal["tools", "save_memory"]:
    """条件边路由函数：判断 agent 输出是否需要调用工具。

    依据：最后一条消息（AIMessage）是否携带 tool_calls。
    - 有 → 走 tools 节点执行工具（执行完回 agent 再判断）
    - 无 → 走 save_memory 节点（提取长期记忆）后结束
    """
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return "save_memory"


def _build_graph():
    graph = StateGraph(AgentState)

    # 节点：load_memory（记忆加载）+ agent（推理）+ tools（工具）+ save_memory（记忆提取）
    graph.add_node("load_memory", load_memory_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(ALL_TOOLS))
    graph.add_node("save_memory", save_memory_node)

    # 入口 → 先加载长期记忆 → 再推理
    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "agent")

    # 条件边：agent 之后按 should_continue 分叉
    graph.add_conditional_edges(
        "agent", should_continue, {"tools": "tools", "save_memory": "save_memory"}
    )

    # 工具执行完 → 回到 agent 继续推理（结果已在 state.messages 里）
    graph.add_edge("tools", "agent")

    # 记忆提取完 → 结束
    graph.add_edge("save_memory", END)

    return graph.compile()


@lru_cache(maxsize=1)
def get_agent():
    """获取编译后的 Agent 图（进程内单例，线程安全）"""
    logger.info("compiling xuan-shu agent graph (memory + tool loop)")
    return _build_graph()
