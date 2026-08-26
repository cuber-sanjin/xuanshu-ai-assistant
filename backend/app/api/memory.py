# Memory REST API：前端 MemoryPanel 使用的 JSON 接口

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.memory.long_term import DEFAULT_USER_ID, delete_memory, list_memories
from app.schemas.memory import MemoryOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memories", tags=["memory"])


@router.get("", response_model=list[MemoryOut], summary="获取全部长期记忆")
def get_memories(db: Session = Depends(get_db)):
    return list_memories(db, DEFAULT_USER_ID)


@router.delete("/{memory_id}", status_code=204, summary="删除一条记忆")
def remove_memory(memory_id: int, db: Session = Depends(get_db)):
    if not delete_memory(db, DEFAULT_USER_ID, memory_id):
        raise HTTPException(status_code=404, detail=f"记忆 {memory_id} 不存在")
