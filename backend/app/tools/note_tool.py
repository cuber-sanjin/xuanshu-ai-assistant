# Note 工具：笔记的存取查删（Agent 对话内调用）
# 与 todo_tool 同模式：每操作独立 session，返回文本给 LLM
# Phase R：写入时同步生成向量索引，检索升级为"语义+关键词"混合召回（fail-open）

import logging

from langchain_core.tools import tool

from app.database.database import SessionLocal
from app.database.models import Note
from app.rag.hybrid import search_notes_hybrid
from app.rag.vector_store import ENTITY_NOTE, delete_embedding, upsert_embedding
from app.services.embeddings import EmbeddingDisabled, embed_text

logger = logging.getLogger(__name__)

DEFAULT_USER_ID = 1

# 嵌入索引：开关关闭或 API 失败时静默跳过（写路径绝不阻塞）
def _index_note(note_id: int, user_id: int, content: str) -> None:
    try:
        vector = embed_text(content)
    except EmbeddingDisabled:
        return
    except Exception as exc:
        logger.warning("note %d 向量生成失败（跳过索引）: %s", note_id, exc)
        return
    with SessionLocal() as db:
        upsert_embedding(db, user_id, ENTITY_NOTE, note_id, vector)


@tool
def save_note(content: str) -> str:
    """保存一条笔记。

    当用户说"帮我记一下/记笔记/记下来"时调用，content 为笔记内容。
    """
    with SessionLocal() as db:
        note = Note(user_id=DEFAULT_USER_ID, content=content)
        db.add(note)
        db.commit()
        db.refresh(note)
    # 向量索引（独立 session，失败不影响保存结果）
    _index_note(note.id, DEFAULT_USER_ID, content)
    return f"笔记已保存 (ID={note.id}): {content[:50]}{'...' if len(content) > 50 else ''}"


@tool
def search_notes(keyword: str) -> str:
    """搜索笔记。

    当用户问"我之前记过什么/查一下笔记/关于 XX 记过什么"时调用。
    支持语义搜索：即使没记过关键词，含义相近的笔记也能找到。
    """
    try:
        with SessionLocal() as db:
            notes = search_notes_hybrid(db, DEFAULT_USER_ID, keyword)
    except Exception:
        # 兜底：混合检索自身异常时回退纯 LIKE（fail-open 最底层防线）
        logger.exception("混合检索失败，回退 LIKE")
        with SessionLocal() as db:
            notes = (
                db.query(Note)
                .filter(
                    Note.user_id == DEFAULT_USER_ID,
                    Note.content.contains(keyword),
                )
                .order_by(Note.created_at.desc())
                .all()
            )
    if not notes:
        return f"没有找到与「{keyword}」相关的笔记"
    lines = [f"[{n.id}] {n.content}" for n in notes[:5]]
    return f"找到 {len(notes)} 条相关笔记:\n" + "\n".join(lines)


@tool
def delete_note(note_id: int) -> str:
    """删除一条笔记。

    当用户说"删除某条笔记"时调用，参数 note_id 为笔记编号。
    """
    with SessionLocal() as db:
        note = db.get(Note, note_id)
        if note is None:
            return f"未找到 ID={note_id} 的笔记"
        content = note.content[:30]
        db.delete(note)
        db.commit()
    # 同步清理向量索引（幂等：没有也不报错）
    with SessionLocal() as db:
        delete_embedding(db, ENTITY_NOTE, note_id)
    return f"已删除笔记: {content}..."
