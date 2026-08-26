# 向量存取层：SQLite 持久化 + 纯 Python 余弦相似度
#
# 为什么不用向量数据库（FAISS/pgvector/sqlite-vec）？
#   - 个人助手的语料量级（笔记+记忆，数百条）：全量加载内存做暴力余弦毫秒级完成
#   - 零新依赖、跨平台（Windows/macOS/Linux 一致）、零运维
#   - 演进路径：数据量 >1 万条时再引入 ANN 索引（sqlite-vec/FAISS），
#     本模块的接口（load_embeddings/top_k_similar）可无痛替换实现
#
# 为什么不用 numpy？
#   - venv 未装 numpy；1024 维 × 数百条 = 数十万次乘加，纯 Python 可接受
#   - 避免为一个小功能引入重型依赖（numpy 是"千行千项"场景才需要的）

import json
import math
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.database.models import Embedding

# 实体类型常量（与调用方约定，避免散落魔法字符串）
ENTITY_NOTE = "note"
ENTITY_MEMORY = "memory"


# ===== 写入 =====

def upsert_embedding(
    db: Session,
    user_id: int,
    entity_type: str,
    entity_id: int,
    vector: list[float],
) -> None:
    """保存/覆盖一条向量（同实体幂等）。

    用 SQLite 的 INSERT ... ON CONFLICT DO UPDATE（依赖 uq_embedding_entity 唯一约束），
    避免"先查再插"的竞态与两次往返。
    """
    stmt = sqlite_insert(Embedding).values(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        vector=json.dumps(vector),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["entity_type", "entity_id"],
        set_={"user_id": user_id, "vector": json.dumps(vector)},
    )
    db.execute(stmt)
    db.commit()


def delete_embedding(db: Session, entity_type: str, entity_id: int) -> None:
    """删除一条向量（实体被删时同步清理）。"""
    db.execute(
        delete(Embedding).where(
            Embedding.entity_type == entity_type,
            Embedding.entity_id == entity_id,
        )
    )
    db.commit()


def delete_embeddings_by_type(db: Session, entity_type: str) -> None:
    """删除某一类实体的全部向量（backfill 重建前清空用）。"""
    db.execute(delete(Embedding).where(Embedding.entity_type == entity_type))
    db.commit()


# ===== 读取与相似度 =====

def load_embeddings(db: Session, user_id: int) -> list[tuple[str, int, list[float]]]:
    """按用户加载全部向量：[(entity_type, entity_id, vector), ...]。

    个人量级全量加载足够；如需优化可改成流式/分页。
    """
    rows = db.execute(
        select(Embedding).where(Embedding.user_id == user_id)
    ).scalars().all()
    return [
        (row.entity_type, row.entity_id, json.loads(row.vector))
        for row in rows
    ]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """两个向量的余弦相似度（纯 Python，禁 numpy）。

    Args:
        a: 向量 A
        b: 向量 B

    Returns:
        [-1, 1] 的相似度；任一向量为零向量时返回 0（避免除零）

    Raises:
        ValueError: 两向量维度不一致
    """
    if len(a) != len(b):
        raise ValueError(f"向量维度不一致: {len(a)} vs {len(b)}")
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def top_k_similar(
    query_vec: list[float],
    items: Iterable[tuple[str, int, list[float]]],
    k: int = 5,
) -> list[tuple[str, int, float]]:
    """返回与查询向量最相似的 top-k 条。

    Args:
        query_vec: 查询向量
        items: (entity_type, entity_id, vector) 候选集
        k: 返回条数

    Returns:
        [(entity_type, entity_id, score), ...] 按相似度降序
    """
    scored = [
        (entity_type, entity_id, cosine_similarity(query_vec, vec))
        for entity_type, entity_id, vec in items
    ]
    scored.sort(key=lambda t: t[2], reverse=True)
    return scored[:k]
