# 长期记忆测试：保存/去重/召回/搜索/删除（走临时测试库）

from app.database.database import SessionLocal
from app.memory.long_term import (
    delete_memory,
    get_relevant_memories,
    list_memories,
    save_memories,
)
from app.rag.hybrid import search_memories_hybrid as search_memories


def test_save_and_list():
    with SessionLocal() as db:
        ids = save_memories(db, 777, [("goal", "用户正在准备面试", 0.8)])
        assert len(ids) == 1

        memories = list_memories(db, 777)
        assert len(memories) == 1
        assert memories[0].memory_type == "goal"
        assert memories[0].content == "用户正在准备面试"


def test_dedupe():
    """相同内容不重复插入（防 extractor 与 remember 工具双写）"""
    with SessionLocal() as db:
        ids1 = save_memories(db, 777, [("learning", "用户在学习 FastAPI", 0.6)])
        ids2 = save_memories(db, 777, [("learning", "用户在学习 FastAPI", 0.9)])
        assert len(ids1) == 1
        assert len(ids2) == 0  # 重复内容被跳过


def test_relevance_ranking():
    """召回按 importance 降序"""
    with SessionLocal() as db:
        save_memories(db, 777, [("habit", "低重要性习惯", 0.2)])
        save_memories(db, 777, [("goal", "高重要性目标", 0.9)])

        relevant = get_relevant_memories(db, 777)
        # 0.9 的排最前
        assert relevant[0].content == "高重要性目标"


def test_search():
    with SessionLocal() as db:
        save_memories(db, 777, [("preference", "用户喜欢晚上学习", 0.5)])
        hits = search_memories(db, 777, "晚上")
        assert len(hits) == 1
        assert "晚上" in hits[0].content

        misses = search_memories(db, 777, "不存在的关键词xyz")
        assert len(misses) == 0


def test_delete():
    with SessionLocal() as db:
        ids = save_memories(db, 777, [("profile", "用户来自北京", 0.7)])
        mem_id = ids[0]

        assert delete_memory(db, 777, mem_id) is True
        assert delete_memory(db, 777, mem_id) is False  # 已删
        assert delete_memory(db, 777, 999999) is False  # 不存在


def test_invalid_type_rejected():
    with SessionLocal() as db:
        ids = save_memories(db, 777, [("bad_type", "非法类型", 0.5)])
        assert len(ids) == 0  # 非法 memory_type 被过滤
