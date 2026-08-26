# Memory 工具：Agent 主动管理长期记忆
# 与"自动提取"（save_memory 节点）互补：
#   - 自动提取：对话后静默判断是否值得记（覆盖面广）
#   - 本工具：用户明确说"记住 XX"时 Agent 主动写入（意图明确）
# 两者共用 long_term.save_memories，自带内容去重，不会双写。

from langchain_core.tools import tool

from app.database.database import SessionLocal
from app.memory.long_term import (
    DEFAULT_USER_ID,
    delete_memory as _delete,
    save_memories,
)
from app.rag.hybrid import search_memories_hybrid

# 默认记忆类型：用户主动"记住"的按重要事件/偏好处理
DEFAULT_MEMORY_TYPE = "important_event"


@tool
def remember(content: str, memory_type: str = DEFAULT_MEMORY_TYPE) -> str:
    """把一条信息存入长期记忆。

    当用户明确说"记住…""以后要记得…"时调用。
    参数：content=要记住的内容；memory_type=类型（preference/profile/goal/learning/habit/important_event）。
    """
    with SessionLocal() as db:
        ids = save_memories(db, DEFAULT_USER_ID, [(memory_type, content, 0.8)])
    if ids:
        return f"已记住: {content}"
    return f"这条信息之前已经记住了: {content}"


@tool
def recall_memory(keyword: str) -> str:
    """搜索关于用户的长期记忆。

    当用户问"我之前说过什么/我有什么目标/我记得……"时调用。
    参数：keyword=关键词。
    """
    with SessionLocal() as db:
        # 语义+关键词混合召回（嵌入不可用时内部降级为纯 LIKE）
        memories = search_memories_hybrid(db, DEFAULT_USER_ID, keyword)
    if not memories:
        return f"没有找到与「{keyword}」相关的记忆"
    lines = [f"[{m.id}] ({m.memory_type}) {m.content}" for m in memories]
    return f"找到 {len(memories)} 条相关记忆:\n" + "\n".join(lines)


@tool
def forget_memory(memory_id: int) -> str:
    """删除一条长期记忆。

    当用户说"忘掉/删除某条记忆"时调用，参数 memory_id 为记忆编号。
    """
    with SessionLocal() as db:
        ok = _delete(db, DEFAULT_USER_ID, memory_id)
    return f"已删除记忆 #{memory_id}" if ok else f"未找到记忆 #{memory_id}"
