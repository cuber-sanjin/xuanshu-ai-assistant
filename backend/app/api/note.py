# Note REST API：前端用的 JSON 接口
# Phase R：REST 创建/删除与工具同埋点（向量索引），q 搜索升级为混合召回

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import SessionLocal, get_db
from app.database.models import Note
from app.rag.hybrid import search_notes_hybrid
from app.rag.vector_store import ENTITY_NOTE, delete_embedding, upsert_embedding
from app.schemas.note import NoteCreate, NoteOut
from app.services.embeddings import EmbeddingDisabled, embed_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notes", tags=["note"])

DEFAULT_USER_ID = 1


def _index_note(note_id: int, content: str) -> None:
    """为笔记生成并保存向量索引（独立 session；失败仅告警，绝不阻断写路径）。"""
    try:
        vector = embed_text(content)
    except EmbeddingDisabled:
        return
    except Exception as exc:
        logger.warning("note %d 向量生成失败（跳过索引）: %s", note_id, exc)
        return
    with SessionLocal() as db:
        upsert_embedding(db, DEFAULT_USER_ID, ENTITY_NOTE, note_id, vector)


@router.get("", response_model=list[NoteOut], summary="获取笔记（关键词或语义搜索）")
def list_notes(
    q: str | None = Query(None, description="关键词/语义搜索，可选"),
    db: Session = Depends(get_db),
):
    if q:
        # 语义+关键词混合召回（嵌入不可用时内部降级为纯 LIKE）
        return search_notes_hybrid(db, DEFAULT_USER_ID, q)
    return (
        db.query(Note)
        .filter(Note.user_id == DEFAULT_USER_ID)
        .order_by(Note.created_at.desc())
        .all()
    )


@router.post("", response_model=NoteOut, status_code=201, summary="创建笔记")
def create_note(payload: NoteCreate, db: Session = Depends(get_db)):
    note = Note(user_id=DEFAULT_USER_ID, content=payload.content)
    db.add(note)
    db.commit()
    db.refresh(note)
    # 向量索引（写路径之外，失败不影响创建结果）
    _index_note(note.id, payload.content)
    logger.info("note created id=%d", note.id)
    return note


@router.delete("/{note_id}", status_code=204, summary="删除笔记")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail=f"笔记 {note_id} 不存在")
    db.delete(note)
    db.commit()
    # 清理向量索引（幂等）
    delete_embedding(db, ENTITY_NOTE, note_id)
