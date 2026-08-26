# Todo 工具：待办事项的增删改查（Agent 对话内调用）
# 与 REST API（api/todo.py）共享同一套数据库操作，但视角不同：
#   - 本文件：LLM 调用的工具，返回人类可读文本
#   - api/todo.py：前端调用的 JSON 接口
# 会话策略：每操作开一个新 session（with SessionLocal() as db），用完即关，
# 避免 session 跨线程/跨请求复用。

from langchain_core.tools import tool

from app.database.database import SessionLocal
from app.database.models import Todo

# MVP 单用户模式：固定用户 ID
DEFAULT_USER_ID = 1


def _to_text(todo: Todo) -> str:
    """把 ORM 对象格式化为文本（给 LLM 读）"""
    status = "已完成" if todo.completed else "未完成"
    due = f"，截止 {todo.due_time}" if todo.due_time else ""
    return f"[{todo.id}] {todo.title}（{status}{due}）"


@tool
def create_todo(title: str, due_time: str | None = None) -> str:
    """创建一条待办事项。

    当用户说"帮我记/添加/安排一个待办"时调用。
    参数：title=待办内容（必填）；due_time=截止时间（可选，如"2026-08-23 15:00"）。
    """
    with SessionLocal() as db:
        todo = Todo(user_id=DEFAULT_USER_ID, title=title, due_time=due_time)
        db.add(todo)
        db.commit()
        db.refresh(todo)
        return f"已创建待办: {_to_text(todo)}"


@tool
def get_todos() -> str:
    """查询所有待办事项（含完成状态）。

    当用户问"我有什么待办/今天有什么安排/还有什么没做"时调用。
    """
    with SessionLocal() as db:
        todos = (
            db.query(Todo)
            .filter(Todo.user_id == DEFAULT_USER_ID)
            .order_by(Todo.completed, Todo.created_at.desc())
            .all()
        )
    if not todos:
        return "当前没有待办事项"
    lines = [f"{'已' if t.completed else '未'}完成: {_to_text(t)}" for t in todos]
    return "待办事项如下:\n" + "\n".join(lines)


@tool
def complete_todo(todo_id: int) -> str:
    """将某条待办事项标记为已完成。

    当用户说"完成/搞定 XX 待办"时调用，参数 todo_id 为待办编号（见待办列表）。
    """
    with SessionLocal() as db:
        todo = db.get(Todo, todo_id)
        if todo is None:
            return f"未找到 ID={todo_id} 的待办"
        todo.completed = True
        db.commit()
        return f"已完成: {todo.title}"


@tool
def delete_todo(todo_id: int) -> str:
    """删除某条待办事项。

    当用户说"删除/划掉 XX 待办"时调用，参数 todo_id 为待办编号。
    """
    with SessionLocal() as db:
        todo = db.get(Todo, todo_id)
        if todo is None:
            return f"未找到 ID={todo_id} 的待办"
        title = todo.title
        db.delete(todo)
        db.commit()
        return f"已删除待办: {title}"
