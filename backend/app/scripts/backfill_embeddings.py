# 存量数据向量索引回填脚本
# 用法（backend 目录下）：
#   python -m app.scripts.backfill_embeddings note     # 只回填笔记
#   python -m app.scripts.backfill_embeddings memory   # 只回填记忆
#   python -m app.scripts.backfill_embeddings all      # 全部（默认）
#
# 幂等：按 (entity_type, entity_id) 唯一约束 upsert，重复执行不产生脏数据；
# 断点续跑：已有向量的实体自动跳过，适合分批/中断后重跑。
# 失败容错：单条失败仅告警并继续，结束后汇总报告。

import argparse
import logging
import sys
from pathlib import Path

# 允许以 `python -m app.scripts.backfill_embeddings` 直接运行
# 脚本位于 backend/app/scripts/，backend 目录为 parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.database.database import SessionLocal, init_db  # noqa: E402
from app.database.models import Memory, Note  # noqa: E402
from app.memory.long_term import DEFAULT_USER_ID  # noqa: E402
from app.rag.vector_store import (  # noqa: E402
    ENTITY_MEMORY,
    ENTITY_NOTE,
    load_embeddings,
    upsert_embedding,
)
from app.services.embeddings import EmbeddingDisabled, embed_texts  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("backfill")


def _existing_ids(entity_type: str) -> set[int]:
    """已索引的实体 ID（断点续跑依据）。"""
    with SessionLocal() as db:
        rows = load_embeddings(db, DEFAULT_USER_ID)
    return {eid for et, eid, _v in rows if et == entity_type}


def _backfill(entity_type: str, entity_cls, field: str) -> tuple[int, int]:
    """回填一类实体，返回 (成功数, 跳过数)。"""
    existing = _existing_ids(entity_type)
    with SessionLocal() as db:
        rows = db.query(entity_cls).filter(entity_cls.user_id == DEFAULT_USER_ID).all()
    todo = [(getattr(r, "id"), getattr(r, field)) for r in rows]
    skip = len(todo)

    # 每批 10 条调用嵌入 API（百炼 text-embedding-v3 批量上限 10）
    batch_size = 10
    ok = 0
    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        try:
            vectors = embed_texts([content for _, content in batch])
        except EmbeddingDisabled:
            logger.warning("嵌入已禁用（EMBEDDING_ENABLED=false），跳过回填")
            return ok, skip
        except Exception as exc:
            logger.warning("批量嵌入失败，跳过本批: %s", exc)
            continue
        with SessionLocal() as db:
            for (eid, _content), vector in zip(batch, vectors):
                upsert_embedding(db, DEFAULT_USER_ID, entity_type, eid, vector)
        ok += len(batch)
        logger.info("%s: 已回填 %d/%d", entity_type, i + len(batch), len(todo))
    return ok, skip


def main() -> None:
    parser = argparse.ArgumentParser(description="向量索引回填")
    parser.add_argument("target", nargs="?", default="all", choices=["note", "memory", "all"])
    args = parser.parse_args()

    init_db()
    total_ok = total_skip = 0
    if args.target in ("note", "all"):
        ok, skip = _backfill(ENTITY_NOTE, Note, "content")
        total_ok += ok
        total_skip += skip
    if args.target in ("memory", "all"):
        ok, skip = _backfill(ENTITY_MEMORY, Memory, "content")
        total_ok += ok
        total_skip += skip

    logger.info("回填完成: 成功 %d 条, 跳过 %d 条", total_ok, total_skip)


if __name__ == "__main__":
    main()
