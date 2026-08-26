# 长期记忆：memories 表的存取（Phase 6）
# 与短期记忆（short_term.py）的区别：
#   - 短期：按会话隔离，只服务当前对话上下文
#   - 长期：跨会话共享（按 user 维度），服务"了解用户"这一目标
#
# 召回策略（Phase R 起）：
#   语义优先（向量 + RRF）→ importance 兜底；开关关闭时与旧版行为一致。
#   RAG 相关逻辑在 app/rag/hybrid.py（search_memories_hybrid / recall_memories_hybrid）。

import logging
from typing import Sequence

from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.database.models import Memory
from app.rag.vector_store import ENTITY_MEMORY, delete_embedding, upsert_embedding
from app.services.embeddings import EmbeddingDisabled, embed_texts

logger = logging.getLogger(__name__)

# 每次对话注入的记忆条数上限（防止上下文膨胀）
MAX_INJECT_MEMORIES = 5

# 合法的记忆类型（与 extractor.py 的 Literal 保持一致）
MEMORY_TYPES = {
    "preference",  # 偏好
    "profile",  # 个人资料
    "goal",  # 目标
    "learning",  # 学习
    "habit",  # 习惯
    "important_event",  # 重要事件
}

DEFAULT_USER_ID = 1


def save_memories(
    db: Session,
    user_id: int,
    items: Sequence[tuple[str, str, float]],
) -> list[int]:
    """批量保存记忆，返回新插入的 ID 列表。

    items: [(memory_type, content, importance), ...]
    去重：内容完全相同的记忆不重复插入（防 extractor 与 remember 工具双写）。
    """
    inserted_ids: list[int] = []
    for memory_type, content, importance in items:
        if memory_type not in MEMORY_TYPES:
            logger.warning("skip invalid memory_type=%s", memory_type)
            continue

        # 去重：同 user 已有相同内容则跳过
        exists = (
            db.query(Memory)
            .filter(Memory.user_id == user_id, Memory.content == content)
            .first()
        )
        if exists:
            continue

        mem = Memory(
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            importance=importance,
        )
        db.add(mem)
        db.flush()  # 拿 ID 不提交（最后统一 commit）
        inserted_ids.append(mem.id)

    if inserted_ids:
        db.commit()
        logger.info("saved %d memories", len(inserted_ids))
        # Phase R：为新记忆生成向量索引（独立 session；失败仅告警，不影响保存）
        _index_new_memories(user_id, inserted_ids)
    return inserted_ids


def _index_new_memories(user_id: int, ids: list[int]) -> None:
    """为新插入的记忆批量生成向量索引（写入路径之外，fail-open）。"""
    try:
        with SessionLocal() as db:
            rows = (
                db.query(Memory)
                .filter(Memory.id.in_(ids))
                .all()
            )
            contents = [(m.id, m.content) for m in rows]
        if not contents:
            return
        vectors = embed_texts([c for _, c in contents])
    except EmbeddingDisabled:
        return
    except Exception as exc:
        logger.warning("memories %s 向量生成失败（跳过索引）: %s", ids, exc)
        return
    with SessionLocal() as db:
        for (mem_id, _content), vector in zip(contents, vectors):
            upsert_embedding(db, user_id, ENTITY_MEMORY, mem_id, vector)


def get_relevant_memories(db: Session, user_id: int, limit: int = MAX_INJECT_MEMORIES) -> list[Memory]:
    """召回最相关的记忆：重要性降序，同重要性按最近更新在前。"""
    return (
        db.query(Memory)
        .filter(Memory.user_id == user_id)
        .order_by(Memory.importance.desc(), Memory.updated_at.desc())
        .limit(limit)
        .all()
    )


def list_memories(db: Session, user_id: int) -> list[Memory]:
    """列出全部记忆（前端 MemoryPanel 用）。"""
    return (
        db.query(Memory)
        .filter(Memory.user_id == user_id)
        .order_by(Memory.created_at.desc())
        .all()
    )


def delete_memory(db: Session, user_id: int, memory_id: int) -> bool:
    """删除记忆，返回是否找到并删除。"""
    mem = (
        db.query(Memory)
        .filter(Memory.id == memory_id, Memory.user_id == user_id)
        .first()
    )
    if mem is None:
        return False
    db.delete(mem)
    db.commit()
    # 清理向量索引（幂等）
    delete_embedding(db, ENTITY_MEMORY, memory_id)
    return True


def format_memories_for_prompt(memories: Sequence[Memory]) -> str:
    """把记忆对象格式化为注入 system prompt 的文本。"""
    if not memories:
        return ""
    lines = [f"- ({m.memory_type}) {m.content}" for m in memories]
    return "关于用户的长久记忆:\n" + "\n".join(lines)
