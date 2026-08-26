# Todo REST API：前端 TodoPanel 使用的 JSON 接口
# 与 tools/todo_tool.py 共享同一数据模型，但面向"前端 UI"而非"LLM 对话"：
#   - 返回结构化 JSON（Pydantic 序列化）
#   - 同步 def 端点：FastAPI 自动放到线程池执行，不阻塞事件循环
#     （async 端点里同步 DB 操作才需要 run_in_threadpool 包裹）

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Todo
from app.schemas.todo import TodoCreate, TodoOut, TodoUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/todos", tags=["todo"])

# MVP 单用户模式：固定 user_id
DEFAULT_USER_ID = 1


@router.get("", response_model=list[TodoOut], summary="获取所有待办")
def list_todos(db: Session = Depends(get_db)):
    """按未完成在前、创建时间倒序返回待办列表"""
    return (
        db.query(Todo)
        .filter(Todo.user_id == DEFAULT_USER_ID)
        .order_by(Todo.completed, Todo.created_at.desc())
        .all()
    )


@router.post("", response_model=TodoOut, status_code=201, summary="创建待办")
def create_todo(payload: TodoCreate, db: Session = Depends(get_db)):
    todo = Todo(user_id=DEFAULT_USER_ID, title=payload.title, due_time=payload.due_time)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    logger.info("todo created id=%d", todo.id)
    return todo


@router.put("/{todo_id}", response_model=TodoOut, summary="更新待办（完成状态）")
def update_todo(todo_id: int, payload: TodoUpdate, db: Session = Depends(get_db)):
    todo = db.get(Todo, todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail=f"待办 {todo_id} 不存在")
    todo.completed = payload.completed
    db.commit()
    db.refresh(todo)
    return todo


@router.delete("/{todo_id}", status_code=204, summary="删除待办")
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.get(Todo, todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail=f"待办 {todo_id} 不存在")
    db.delete(todo)
    db.commit()
