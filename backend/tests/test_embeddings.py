# 向量存储层测试（纯函数 + SQLite 临时库，零网络）

from app.database.database import SessionLocal
from app.rag.vector_store import (
    cosine_similarity,
    delete_embedding,
    load_embeddings,
    top_k_similar,
    upsert_embedding,
)


def test_cosine_basics():
    # 正交 → 0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0
    # 同向 → 1
    assert abs(cosine_similarity([1, 2], [2, 4]) - 1.0) < 1e-9
    # 自身 → 1
    assert abs(cosine_similarity([1, 0], [1, 0]) - 1.0) < 1e-9
    # 反向 → -1
    assert abs(cosine_similarity([1, 0], [-1, 0]) + 1.0) < 1e-9
    # 零向量 → 0（防除零）
    assert cosine_similarity([0, 0], [1, 1]) == 0.0


def test_cosine_dim_mismatch():
    import pytest

    with pytest.raises(ValueError):
        cosine_similarity([1], [1, 2])


def test_upsert_and_top_k():
    with SessionLocal() as db:
        # 写入两条 + 一条幂等覆盖
        upsert_embedding(db, 1, "note", 1, [1.0, 0.0])
        upsert_embedding(db, 1, "note", 1, [1.0, 0.0])  # 覆盖不报错
        upsert_embedding(db, 1, "memory", 2, [0.0, 1.0])

        rows = load_embeddings(db, 1)
        assert len(rows) == 2  # 幂等：仍是 2 条

        # top_k 排序：与 [1,0] 最相似的是 note/1
        top = top_k_similar([1.0, 0.1], rows, k=1)
        assert top[0][0] == "note"
        assert top[0][1] == 1

        # 按用户隔离
        assert load_embeddings(db, 99) == []

        # 删除
        delete_embedding(db, "note", 1)
        assert len(load_embeddings(db, 1)) == 1
