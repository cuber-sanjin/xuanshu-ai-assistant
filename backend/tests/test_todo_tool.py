# Todo 工具集成测试：走真实 SQLite（测试库），验证工具全链路
# 注意：conftest 已把 XUANSHU_DB_PATH 指向临时库，不污染开发数据

import re

from app.tools.todo_tool import complete_todo, create_todo, delete_todo, get_todos


def _extract_id(text: str) -> int:
    """从工具返回文本里提取待办 ID，如 '[3] 学习 LangGraph' → 3"""
    match = re.search(r"\[(\d+)\]", text)
    assert match, f"无法从返回中提取 ID: {text}"
    return int(match.group(1))


def test_todo_full_crud():
    # 1. 创建
    created = create_todo.invoke({"title": "测试待办事项", "due_time": "2026-08-23 15:00"})
    assert "已创建" in created
    todo_id = _extract_id(created)

    # 2. 查询（应包含新待办）
    todos = get_todos.invoke({})
    assert "测试待办事项" in todos

    # 3. 完成
    done = complete_todo.invoke({"todo_id": todo_id})
    assert "已完成" in done

    # 4. 删除
    deleted = delete_todo.invoke({"todo_id": todo_id})
    assert "已删除" in deleted

    # 5. 确认已删
    todos_after = get_todos.invoke({})
    assert "测试待办事项" not in todos_after


def test_complete_nonexistent():
    result = complete_todo.invoke({"todo_id": 999999})
    assert "未找到" in result


def test_get_empty_or_not():
    """查询接口总能返回可读结果（空列表或内容列表）"""
    result = get_todos.invoke({})
    assert isinstance(result, str) and len(result) > 0
