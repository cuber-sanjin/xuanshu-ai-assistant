# 混合召回测试：RRF 融合 / 语义优先 / 降级路径 / 开关行为（零网络，mock 嵌入）

from unittest.mock import patch

import pytest

from app.config import settings
from app.database.database import SessionLocal
from app.memory.long_term import save_memories
from app.rag.hybrid import rrf_merge, search_memories_hybrid, search_notes_hybrid
from app.rag.vector_store import upsert_embedding
from app.services.embeddings import EmbeddingDisabled

TEST_USER = 9999


def test_rrf_merge():
    """两路排名融合：双路命中的文档排名靠前，纯单路命中的排后。"""
    r1 = [(1, 0.9), (2, 0.8), (3, 0.7)]
    r2 = [(2, 0.9), (1, 0.8), (4, 0.6)]
    fused = rrf_merge([r1, r2], top_k=3)
    ids = [eid for eid, _ in fused]
    # 1、2 都被两路命中 → 必须排在前二
    assert ids[:2] == [1, 2] or ids[:2] == [2, 1]
    assert 3 not in ids[:2]


# ---------- 语义优先：受控假向量 ----------

# 假嵌入：按文本长度映射成 2 维向量（"晚间跑步"与"夜跑锻炼"语义近 → 同方向）
_FAKE_MAP = {
    "晚间跑步三公里": [1.0, 0.0],
    "夜跑锻炼身体": [0.9, 0.1],
    "明天要交周报": [0.0, 1.0],
}


def _fake_embed_text(text: str) -> list[float]:
    return _FAKE_MAP.get(text, [0.5, 0.5])


def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
    return [_fake_embed_text(t) for t in texts]


def test_semantic_search_notes_over_keyword():
    """语义命中 > 关键词命中：查询"夜跑"时，没有"夜跑"字样的笔记也能被召回。"""
    with SessionLocal() as db:
        # 直接写向量 + 实体（绕过 note 工具，聚焦召回逻辑）
        upsert_embedding(db, TEST_USER, "note", 101, [1.0, 0.0])
        upsert_embedding(db, TEST_USER, "note", 102, [0.0, 1.0])
        from app.database.models import Note

        db.add(Note(user_id=TEST_USER, id=101, content="晚间跑步三公里"))
        db.add(Note(user_id=TEST_USER, id=102, content="明天要交周报"))
        db.commit()

        with patch("app.services.embeddings.embed_text", side_effect=_fake_embed_text):
            with patch("app.config.settings.embedding_enabled", True):
                hits = search_notes_hybrid(db, TEST_USER, "夜跑锻炼身体", top_k=5)
        ids = [n.id for n in hits]
        # 语义最相似的 101 必须被召回（即使不包含"夜跑"关键词）
        assert 101 in ids


def test_search_notes_degrades_when_disabled():
    """开关关闭 → 语义不可用 → 降级为纯 LIKE（旧行为）。"""
    from app.database.models import Note

    with SessionLocal() as db:
        db.add(Note(user_id=TEST_USER, id=201, content="包含关键词的笔记"))
        db.commit()
        # embedding_enabled=False 时 embed_text 抛 EmbeddingDisabled
        with patch(
            "app.services.embeddings.embed_text",
            side_effect=EmbeddingDisabled("disabled"),
        ):
            hits = search_notes_hybrid(db, TEST_USER, "关键词")
        assert len(hits) == 1
        assert hits[0].id == 201


def test_search_memories_hybrid_fallback():
    """记忆混合搜索：嵌入异常时降级为 LIKE，不抛错。"""
    with SessionLocal() as db:
        save_memories(db, TEST_USER, [("goal", "今年目标是拿到后端 Offer", 0.9)])

        with patch(
            "app.services.embeddings.embed_text",
            side_effect=RuntimeError("network down"),
        ):
            hits = search_memories_hybrid(db, TEST_USER, "Offer")
        assert len(hits) == 1


def test_rrf_merge_ignores_empty_ranks():
    fused = rrf_merge([[], [(7, 1.0)]], top_k=5)
    assert fused == [(7, pytest.approx(1.0 / 61.0))]
