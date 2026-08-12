"""用例索引同步 — 增量 / 全量写入 Milvus + ES。"""

import asyncio
import hashlib
import time
from datetime import datetime

from elasticsearch import AsyncElasticsearch
from loguru import logger
from pymilvus import Collection
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.aitc.case.models import AiTcCase
from app.aitc.retrieval.case.schemas import CaseIndexData, IndexProgress
from app.aitc.retrieval.common.cleaner import build_vector_text, split_name, steps_to_text, strip_html
from app.aitc.retrieval.common.client import (
    embed_texts,
    ensure_milvus_collection,
    get_es_client,
    get_milvus_collection,
)
from app.aitc.retrieval.common.config import (
    EMBEDDING_DIM,
    ES_INDEX_CASE,
    MILVUS_COLLECTION_CASE,
)


# ════════════════════════════════════════════
# ES 索引 Mapping
# ════════════════════════════════════════════

ES_CASE_MAPPING = {
    "settings": {
        "analysis": {
            "analyzer": {
                "ik_max_word_synonym": {
                    "type": "custom",
                    "tokenizer": "ik_max_word",
                },
                "ik_smart_synonym": {
                    "type": "custom",
                    "tokenizer": "ik_smart",
                    "filter": ["synonym_filter"],
                },
            },
            "filter": {
                "synonym_filter": {
                    "type": "synonym",
                    "synonyms": [],
                    "updateable": True,
                },
            },
        }
    },
    "mappings": {
        "properties": {
            "case_id": {"type": "keyword"},
            "project_id": {"type": "integer"},
            "suite_id": {"type": "integer"},
            "is_core": {"type": "boolean"},
            "importance": {"type": "keyword"},
            "is_sample": {"type": "boolean"},
            "is_deleted": {"type": "boolean"},
            "name_words": {
                "type": "text",
                "analyzer": "ik_max_word_synonym",
                "search_analyzer": "ik_smart_synonym",
            },
            "purpose": {
                "type": "text",
                "analyzer": "ik_max_word_synonym",
                "search_analyzer": "ik_smart_synonym",
            },
            "summary": {
                "type": "text",
                "analyzer": "ik_max_word_synonym",
                "search_analyzer": "ik_smart_synonym",
            },
            "steps_text": {
                "type": "text",
                "analyzer": "ik_max_word_synonym",
                "search_analyzer": "ik_smart_synonym",
            },
            "topo": {
                "type": "text",
                "analyzer": "ik_max_word_synonym",
                "search_analyzer": "ik_smart_synonym",
            },
            "updated_at": {"type": "date"},
        }
    },
}

# Milvus Collection Schema
MILVUS_CASE_FIELDS = [
    {"name": "case_id", "dtype": "INT64", "is_primary": True},
    {"name": "vector", "dtype": "FLOAT_VECTOR", "dim": EMBEDDING_DIM},
    {"name": "project_id", "dtype": "INT64"},
    {"name": "suite_id", "dtype": "INT64"},
    {"name": "is_core", "dtype": "BOOL"},
    {"name": "is_sample", "dtype": "BOOL"},
    {"name": "is_deleted", "dtype": "BOOL"},
]


# ════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════

def _compute_index_hash(case: AiTcCase) -> str:
    """计算索引内容 SHA256（只覆盖参与索引的字段）。"""
    raw = "|".join([
        case.name or "",
        case.purpose or "",
        case.summary or "",
        str(case.steps or ""),
        case.topo or "",
        str(case.importance),
        str(case.is_core),
        str(case.is_sample),
        str(case.is_deleted),
        str(case.project_id),
        str(case.suite_id),
    ])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _build_index_data(case: AiTcCase) -> CaseIndexData:
    """将 ORM 模型转为标准化索引数据。"""
    steps_text = steps_to_text(case.steps)

    return CaseIndexData(
        case_id=case.id,
        project_id=case.project_id,
        suite_id=case.suite_id,
        name=case.name or "",
        purpose=case.purpose or "",
        summary=case.summary or "",
        steps_text=steps_text,
        topo=case.topo or "",
        importance=case.importance or 2,
        is_core=bool(case.is_core),
        is_sample=bool(case.is_sample),
        is_deleted=bool(case.is_deleted),
        updated_at=case.update_time.isoformat() if case.update_time else "",
        index_hash=_compute_index_hash(case),
    )


# ════════════════════════════════════════════
# ES 索引管理
# ════════════════════════════════════════════

async def _ensure_es_index() -> None:
    """确保 ES 索引存在，不存在则创建。"""
    es = await get_es_client()
    exists = await es.indices.exists(index=ES_INDEX_CASE)
    if not exists:
        await es.indices.create(index=ES_INDEX_CASE, body=ES_CASE_MAPPING)
        logger.info(f"ES index '{ES_INDEX_CASE}' created")
    # 确保索引已打开
    else:
        logger.info(f"ES index '{ES_INDEX_CASE}' already exists")


async def _index_one_to_es(es: AsyncElasticsearch, data: CaseIndexData) -> None:
    """单条写入 ES。"""
    doc = {
        "case_id": str(data.case_id),
        "project_id": data.project_id,
        "suite_id": data.suite_id,
        "is_core": data.is_core,
        "importance": str(data.importance),
        "is_sample": data.is_sample,
        "is_deleted": data.is_deleted,
        "name_words": split_name(data.name),
        "purpose": data.purpose,
        "summary": data.summary,
        "steps_text": data.steps_text,
        "topo": data.topo,
        "updated_at": data.updated_at,
    }
    await es.index(index=ES_INDEX_CASE, id=str(data.case_id), document=doc)


async def _delete_from_es(es: AsyncElasticsearch, case_id: int) -> None:
    """从 ES 删除单条。"""
    try:
        await es.delete(index=ES_INDEX_CASE, id=str(case_id))
    except Exception:
        pass  # 404 忽略


# ════════════════════════════════════════════
# Milvus 索引管理
# ════════════════════════════════════════════

def _ensure_milvus_collection() -> Collection:
    """确保 Milvus Collection 存在。"""
    return ensure_milvus_collection(
        name=MILVUS_COLLECTION_CASE,
        fields=MILVUS_CASE_FIELDS,
        description="测试用例向量索引",
    )


async def _index_one_to_milvus(collection: Collection, data: CaseIndexData, vector: list[float]) -> None:
    """单条写入 Milvus。"""
    import numpy as np

    # 先删除旧的
    try:
        collection.delete(f'case_id in [{data.case_id}]')
    except Exception:
        pass

    # 软删除的用例不写入
    if data.is_deleted:
        return

    entity = [
        [data.case_id],                # case_id
        [np.array(vector, dtype=np.float32)],  # vector
        [data.project_id],             # project_id
        [data.suite_id],               # suite_id
        [data.is_core],                # is_core
        [data.is_sample],              # is_sample
        [data.is_deleted],             # is_deleted
    ]
    collection.insert(entity)
    collection.flush()


async def _delete_from_milvus(collection: Collection, case_id: int) -> None:
    """从 Milvus 删除单条。"""
    try:
        collection.delete(f'case_id in [{case_id}]')
        collection.flush()
    except Exception:
        pass


# ════════════════════════════════════════════
# 同步逻辑
# ════════════════════════════════════════════

async def _update_case_index_hash(db: AsyncSession, case_id: int, index_hash: str) -> None:
    """更新 case 的 index_hash 和 indexed_at。"""
    await db.execute(
        update(AiTcCase)
        .where(AiTcCase.id == case_id)
        .values(index_hash=index_hash, indexed_at=datetime.utcnow())
    )
    await db.commit()


async def index_single(db: AsyncSession, case_id: int) -> bool:
    """增量索引单条用例。

    Returns: True 表示已写入，False 表示跳过（内容未变）。
    """
    es = await get_es_client()
    coll = _ensure_milvus_collection()

    result = await db.execute(select(AiTcCase).where(AiTcCase.id == case_id))
    case = result.scalar_one_or_none()
    if case is None:
        return False

    data = _build_index_data(case)

    # 增量检测：hash 相同则跳过
    if case.index_hash and case.index_hash == data.index_hash:
        return False

    # 向量化（同步调用，run_in_executor）
    vector_text = build_vector_text(
        name=data.name,
        purpose=data.purpose,
        summary=data.summary,
        steps_text=data.steps_text,
        topo=data.topo,
    )
    vectors = await asyncio.get_event_loop().run_in_executor(None, embed_texts, [vector_text])
    vector = vectors[0]

    # 软删除的用例：从 ES/Milvus 删除
    if data.is_deleted:
        await _delete_from_es(es, data.case_id)
        await _delete_from_milvus(coll, data.case_id)
        await _update_case_index_hash(db, data.case_id, data.index_hash)
        return True

    # 写入 ES + Milvus
    await _index_one_to_es(es, data)
    await _index_one_to_milvus(coll, data, vector)

    # 更新追踪字段
    await _update_case_index_hash(db, data.case_id, data.index_hash)

    return True


async def index_batch(db: AsyncSession, case_ids: list[int]) -> IndexProgress:
    """批量索引（增量模式）。"""
    progress = IndexProgress(total=len(case_ids))

    for case_id in case_ids:
        try:
            written = await index_single(db, case_id)
            if written:
                progress.indexed += 1
            else:
                progress.skipped += 1
        except Exception as e:
            progress.failed += 1
            progress.errors.append(f"case_id={case_id}: {e}")
            logger.error(f"Index failed for case_id={case_id}: {e}")

    return progress


async def reindex_all(db: AsyncSession) -> IndexProgress:
    """全量重建索引。"""
    await _ensure_es_index()

    # 查询所有用例 ID（含已删除）
    result = await db.execute(
        select(AiTcCase.id).order_by(AiTcCase.id)
    )
    all_ids = [row[0] for row in result.fetchall()]

    logger.info(f"Reindex all: {len(all_ids)} cases")

    # 全量重建：强制重新计算（清空 index_hash 跳过检测）
    progress = IndexProgress(total=len(all_ids))

    for case_id in all_ids:
        try:
            # 全量模式强制写入
            await _force_reindex_one(db, case_id)
            progress.indexed += 1
        except Exception as e:
            progress.failed += 1
            progress.errors.append(f"case_id={case_id}: {e}")
            logger.error(f"Reindex failed for case_id={case_id}: {e}")

    return progress


async def _force_reindex_one(db: AsyncSession, case_id: int) -> None:
    """全量重建时不检测 hash，直接覆盖写入。"""
    es = await get_es_client()
    coll = _ensure_milvus_collection()

    result = await db.execute(select(AiTcCase).where(AiTcCase.id == case_id))
    case = result.scalar_one_or_none()
    if case is None:
        return

    data = _build_index_data(case)

    # 软删除的不写入
    if data.is_deleted:
        await _delete_from_es(es, data.case_id)
        await _delete_from_milvus(coll, data.case_id)
        await _update_case_index_hash(db, data.case_id, data.index_hash)
        return

    vector_text = build_vector_text(
        name=data.name,
        purpose=data.purpose,
        summary=data.summary,
        steps_text=data.steps_text,
        topo=data.topo,
    )
    vectors = await asyncio.get_event_loop().run_in_executor(None, embed_texts, [vector_text])
    vector = vectors[0]

    await _index_one_to_es(es, data)
    await _index_one_to_milvus(coll, data, vector)
    await _update_case_index_hash(db, data.case_id, data.index_hash)
