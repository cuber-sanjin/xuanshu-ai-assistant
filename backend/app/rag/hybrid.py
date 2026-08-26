# 混合召回：语义（向量）与词法（SQL LIKE）双路检索 + RRF 融合
#
# 为什么用 RRF（Reciprocal Rank Fusion）而不是加权求和？（面试点）
#   - 免调参：无需为语义/词法权重试错，k=60 是通用经验值
#   - 尺度无关：两路的"排名"天然可比（1/rank），分数分布不同也不影响
#   - 共命中文档自动加权：同时被两路命中的文档分数叠加，天然排前
#
# 召回公式：score(id) = Σ 1 / (k + rank)，k=60

import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import Memory, Note
from app.memory.long_term import DEFAULT_USER_ID, MAX_INJECT_MEMORIES
from app.rag.vector_store import (
    ENTITY_MEMORY,
    ENTITY_NOTE,
    load_embeddings,
    top_k_similar,
)
from app.services.embeddings import EmbeddingDisabled, get_query_embedding

logger = logging.getLogger(__name__)

# RRF 常量
RRF_K = 60
# 语义/词法每路取前 N 条参与融合
SEMANTIC_CANDIDATES = 20
LEXICAL_CANDIDATES = 20


def rrf_merge(
    ranked_lists: list[list[tuple[int, float]]],
    k: int = RRF_K,
    top_k: int = 5,
) -> list[tuple[int, float]]:
    """多路排名列表 → RRF 融合后的 top-k。

    Args:
        ranked_lists: 每路为 [(entity_id, score), ...]（score 仅用于最终排序）
        k: RRF 平滑常数
        top_k: 返回条数

    Returns:
        [(entity_id, rrf_score), ...] 降序
    """
    fused: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, (entity_id, _score) in enumerate(ranked, start=1):
            fused[entity_id] = fused.get(entity_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(fused.items(), key=lambda t: t[1], reverse=True)
    return ordered[:top_k]


# ===== 笔记混合检索 =====

def search_notes_hybrid(
    db: Session,
    user_id: int,
    query: str,
    top_k: int = 5,
) -> list[Note]:
    """笔记语义优先检索：向量召回 + LIKE 召回 → RRF 融合。

    fail-open：嵌入不可用（开关关/API 失败）时降级为纯 LIKE，行为与旧版一致。
    """
    # --- 词法路（始终可用） ---
    lexical = (
        db.query(Note)
        .filter(Note.user_id == user_id, Note.content.contains(query))
        .order_by(Note.created_at.desc())
        .limit(LEXICAL_CANDIDATES)
        .all()
    )
    lexical_ranked = [(n.id, 0.0) for n in lexical]

    # --- 语义路（可能不可用） ---
    try:
        query_vec = get_query_embedding(query)
        vectors = load_embeddings(db, user_id)
        note_vectors = [(e, i, v) for e, i, v in vectors if e == ENTITY_NOTE]
        semantic = top_k_similar(query_vec, note_vectors, k=SEMANTIC_CANDIDATES)
        semantic_ranked = [(entity_id, score) for _, entity_id, score in semantic]
    except (EmbeddingDisabled, Exception) as exc:
        if not isinstance(exc, EmbeddingDisabled):
            logger.warning("语义检索降级为词法: %s", exc)
        return lexical[:top_k]  # 降级：只返回词法结果（保持旧行为）

    # --- RRF 融合 ---
    fused_ids = rrf_merge([lexical_ranked, semantic_ranked], top_k=top_k)
    # 语义命中的笔记可能不在词法结果中：按 id 补齐实体对象
    by_id = {n.id: n for n in lexical}
    for eid, _score in fused_ids:
        if eid not in by_id:
            note = db.get(Note, eid)
            if note:
                by_id[eid] = note
    ordered = [by_id[eid] for eid, _ in fused_ids if eid in by_id]
    return ordered


# ===== 记忆混合检索 =====

def recall_memories_hybrid(
    db: Session,
    user_id: int,
    query: str,
    top_k: int = MAX_INJECT_MEMORIES,
) -> list[Memory]:
    """记忆语义优先召回（注入对话用）。

    fail-open：嵌入不可用时降级为 importance 排序（旧行为）。
    """
    try:
        query_vec = get_query_embedding(query)
        vectors = load_embeddings(db, user_id)
        memory_vectors = [(e, i, v) for e, i, v in vectors if e == ENTITY_MEMORY]
        semantic = top_k_similar(query_vec, memory_vectors, k=SEMANTIC_CANDIDATES)
        semantic_ranked = [(entity_id, score) for _, entity_id, score in semantic]
    except (EmbeddingDisabled, Exception) as exc:
        if not isinstance(exc, EmbeddingDisabled):
            logger.warning("记忆语义召回降级为 importance: %s", exc)
        return (
            db.query(Memory)
            .filter(Memory.user_id == user_id)
            .order_by(Memory.importance.desc(), Memory.updated_at.desc())
            .limit(top_k)
            .all()
        )

    fused_ids = rrf_merge(
        [semantic_ranked, []],  # 记忆无词法路（旧版非关键词召回），语义单路 + 兜底 importance
        top_k=top_k,
    )
    result: list[Memory] = []
    for eid, _ in fused_ids:
        mem = db.get(Memory, eid)
        if mem:
            result.append(mem)
    # 不足 top_k 时用 importance 兜底补足
    if len(result) < top_k:
        existing = {m.id for m in result}
        extra = (
            db.query(Memory)
            .filter(Memory.user_id == user_id, ~Memory.id.in_(existing or [0]))
            .order_by(Memory.importance.desc(), Memory.updated_at.desc())
            .limit(top_k - len(result))
            .all()
        )
        result.extend(extra)
    return result


# ===== 兼容入口（供工具/节点调用） =====

def get_relevant_memories(
    db: Session,
    user_id: int,
    limit: int = MAX_INJECT_MEMORIES,
    query_text: str | None = None,
) -> list[Memory]:
    """增强版记忆召回：有 query 走语义混合，无 query 走原 importance 逻辑。

    向后兼容：所有旧调用（不传 query_text）行为不变。
    """
    if query_text and settings.embedding_enabled:
        try:
            return recall_memories_hybrid(db, user_id, query_text, top_k=limit)
        except Exception:
            logger.exception("语义召回失败，回退 importance")
    return (
        db.query(Memory)
        .filter(Memory.user_id == user_id)
        .order_by(Memory.importance.desc(), Memory.updated_at.desc())
        .limit(limit)
        .all()
    )


def search_memories_hybrid(
    db: Session,
    user_id: int,
    keyword: str,
) -> list[Memory]:
    """记忆关键词/语义搜索（REST /api/memories?q= 用）。

    语义 + LIKE 融合；嵌入不可用则纯 LIKE（旧行为）。
    """
    lexical = (
        db.query(Memory)
        .filter(Memory.user_id == user_id, Memory.content.contains(keyword))
        .order_by(Memory.importance.desc())
        .limit(LEXICAL_CANDIDATES)
        .all()
    )
    try:
        query_vec = get_query_embedding(keyword)
        vectors = load_embeddings(db, user_id)
        memory_vectors = [(e, i, v) for e, i, v in vectors if e == ENTITY_MEMORY]
        semantic = top_k_similar(query_vec, memory_vectors, k=SEMANTIC_CANDIDATES)
        semantic_ranked = [(entity_id, score) for _, entity_id, score in semantic]
    except Exception:
        return lexical

    fused_ids = rrf_merge(
        [[(n.id, 0.0) for n in lexical], semantic_ranked], top_k=20
    )
    by_id = {n.id: n for n in lexical}
    for eid, _ in fused_ids:
        if eid not in by_id:
            mem = db.get(Memory, eid)
            if mem:
                by_id[eid] = mem
    return [by_id[eid] for eid, _ in fused_ids if eid in by_id]
