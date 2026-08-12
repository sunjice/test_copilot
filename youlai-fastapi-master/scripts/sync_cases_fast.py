#!/usr/bin/env python3
"""批量全量同步用例到 Elasticsearch + Milvus（批量向量化，避免逐条推理超时）。

用法:
    cd youlai-fastapi-master
    python scripts/sync_cases_fast.py
"""

import asyncio
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 环境配置（本地 Docker）
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://youlai:Youlai%402026@localhost:15432/youlai_admin",
)
os.environ.setdefault("ES_HOST", "http://localhost:9200")
os.environ.setdefault("MILVUS_HOST", "localhost")
os.environ.setdefault("MILVUS_PORT", "19530")
os.environ.setdefault("EMBEDDING_DEVICE", "cpu")


async def main():
    import app.aitc.models  # noqa: F401  确保 ORM 全注册
    from app.config import settings
    from app.database import AsyncSessionLocal
    from app.aitc.retrieval.case.indexer import _ensure_es_index, _build_index_data
    from app.aitc.retrieval.case.schemas import IndexProgress
    from app.aitc.retrieval.common.cleaner import build_vector_text
    from app.aitc.retrieval.common.client import (
        embed_texts,
        ensure_milvus_collection,
        get_es_client,
        get_embedding_model,
        close_es_client,
    )
    from app.aitc.retrieval.common.config import MILVUS_COLLECTION_CASE
    from app.aitc.case.models import AiTcCase
    from sqlalchemy import select, update
    from datetime import datetime

    t0 = time.time()
    print("=" * 60)
    print(" 批量全量同步 用例 → ES + Milvus")
    print("=" * 60)
    print(f"  ES={settings.ES_HOST}  Milvus={settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
    print()

    # 1. 读取全部用例
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AiTcCase).order_by(AiTcCase.id)
        )
        cases = result.scalars().all()
        print(f"[1/4] 读取用例: {len(cases)} 条")
        if not cases:
            print("  无数据，退出")
            return

        # 2. 构建索引数据
        print("[2/4] 构建索引数据...")
        datas = [_build_index_data(c) for c in cases]

        # 3. 批量向量化（一次推理全部文本，比逐条快数倍）
        print(f"[3/4] 批量向量化 {len(datas)} 条文本...")
        get_embedding_model()  # 确保模型已加载
        texts = [
            build_vector_text(
                name=d.name,
                purpose=d.purpose,
                summary=d.summary,
                steps_text=d.steps_text,
                topo=d.topo,
            )
            for d in datas
        ]
        loop = asyncio.get_event_loop()
        vectors = await loop.run_in_executor(None, embed_texts, texts)
        print(f"      完成 ({time.time()-t0:.1f}s)")

        # 4. 批量写入 ES + Milvus
        print("[4/4] 写入 ES + Milvus...")
        await _ensure_es_index()
        es = await get_es_client()
        coll = ensure_milvus_collection(
            name=MILVUS_COLLECTION_CASE,
            fields=[
                {"name": "case_id", "dtype": "INT64", "is_primary": True},
                {"name": "vector", "dtype": "FLOAT_VECTOR", "dim": settings.EMBEDDING_DIM},
                {"name": "project_id", "dtype": "INT64"},
                {"name": "suite_id", "dtype": "INT64"},
                {"name": "is_core", "dtype": "BOOL"},
                {"name": "is_sample", "dtype": "BOOL"},
                {"name": "is_deleted", "dtype": "BOOL"},
            ],
            description="测试用例向量索引",
        )

        import numpy as np

        es_ids, es_docs, mv = [], [], {"case_id": [], "vector": [], "project_id": [], "suite_id": [], "is_core": [], "is_sample": [], "is_deleted": []}
        for d, vec in zip(datas, vectors):
            if d.is_deleted:
                continue  # 软删除不写入
            es_ids.append(str(d.case_id))
            es_docs.append({
                "case_id": str(d.case_id),
                "project_id": d.project_id,
                "suite_id": d.suite_id,
                "is_core": d.is_core,
                "importance": str(d.importance),
                "is_sample": d.is_sample,
                "is_deleted": d.is_deleted,
                "name_words": d.name,
                "purpose": d.purpose,
                "summary": d.summary,
                "steps_text": d.steps_text,
                "topo": d.topo,
                "updated_at": d.updated_at,
            })
            # Milvus 列式结构: 每列是一个列表
            mv["case_id"].append(d.case_id)
            mv["vector"].append(np.array(vec, dtype=np.float32))
            mv["project_id"].append(d.project_id)
            mv["suite_id"].append(d.suite_id)
            mv["is_core"].append(d.is_core)
            mv["is_sample"].append(d.is_sample)
            mv["is_deleted"].append(d.is_deleted)

        # ES 批量写入
        from elasticsearch.helpers import async_bulk
        async def gen():
            for cid, doc in zip(es_ids, es_docs):
                yield {"_index": settings.ES_INDEX_CASE, "_id": cid, "_source": doc}
        ok_es, errs = await async_bulk(es, gen(), chunk_size=50, refresh=True)
        print(f"  ES 写入: {ok_es} 条 (errors={errs})")

        # Milvus 批量写入（先删旧再插新）
        try:
            coll.delete("case_id >= 0")
        except Exception:
            pass
        n = len(mv["case_id"])
        if n:
            coll.insert([mv["case_id"], mv["vector"], mv["project_id"], mv["suite_id"],
                         mv["is_core"], mv["is_sample"], mv["is_deleted"]])
            coll.flush()
        print(f"  Milvus 写入: {n} 条")

        # 更新 index_hash / indexed_at
        now = datetime.utcnow()
        for d in datas:
            await db.execute(
                update(AiTcCase)
                .where(AiTcCase.id == d.case_id)
                .values(index_hash=d.index_hash, indexed_at=now)
            )
        await db.commit()
        print(f"  更新追踪字段: {len(datas)} 条")

    await close_es_client()
    print(f"\n完成! 总耗时 {time.time()-t0:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
