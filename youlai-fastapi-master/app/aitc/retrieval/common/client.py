"""ES / Milvus 客户端封装（全局单例）。

Embedding 向量化已抽离到 app.aitc.retrieval.common.embedding 包（provider 注册表
模式，支持 local / ollama / openai / azure），此处 re-export 保持调用方兼容。
"""

import threading
from typing import Any

from elasticsearch import AsyncElasticsearch
from loguru import logger
from pymilvus import (
    Collection,
    connections,
    utility,
)

from app.aitc.retrieval.common.config import (
    ES_HOST,
    ES_INDEX_CASE,
    MILVUS_COLLECTION_CASE,
    MILVUS_HOST,
    MILVUS_PORT,
)
from app.aitc.retrieval.common.embedding import embed_texts, get_embedding_model


# ════════════════════════════════════════════
# Elasticsearch
# ════════════════════════════════════════════

_es_client: AsyncElasticsearch | None = None
_es_lock = threading.Lock()


async def get_es_client() -> AsyncElasticsearch:
    """获取 ES 异步客户端（延迟初始化，线程安全）。"""
    global _es_client
    if _es_client is not None:
        return _es_client

    with _es_lock:
        if _es_client is not None:
            return _es_client
        logger.info(f"Connecting to Elasticsearch at {ES_HOST}")
        _es_client = AsyncElasticsearch(hosts=[ES_HOST])
        logger.info("Elasticsearch connected")
        return _es_client


async def close_es_client() -> None:
    global _es_client
    if _es_client is not None:
        await _es_client.close()
        _es_client = None
        logger.info("Elasticsearch client closed")


# ════════════════════════════════════════════
# Milvus
# ════════════════════════════════════════════

_milvus_connected: bool = False
_milvus_lock = threading.Lock()


def _connect_milvus() -> None:
    """连接 Milvus（同步方法，pymilvus 连接是全局的）。"""
    global _milvus_connected
    if _milvus_connected:
        return

    with _milvus_lock:
        if _milvus_connected:
            return
        logger.info(f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
        connections.connect(alias="default", host=MILVUS_HOST, port=str(MILVUS_PORT))
        _milvus_connected = True
        logger.info("Milvus connected")


def get_milvus_collection(name: str = MILVUS_COLLECTION_CASE) -> Collection:
    """获取 Milvus Collection（连接后返回 Collection 对象）。"""
    _connect_milvus()
    return Collection(name)


def ensure_milvus_collection(name: str, fields: list[dict], description: str = "") -> Collection:
    """确保 Collection 存在，不存在则创建。

    fields 示例：
        [
            {"name": "case_id", "dtype": "INT64", "is_primary": True},
            {"name": "vector", "dtype": "FLOAT_VECTOR", "dim": 1024},
            {"name": "project_id", "dtype": "INT64"},
            ...
        ]
    """
    _connect_milvus()

    if utility.has_collection(name):
        coll = Collection(name)
        coll.load()
        return coll

    from pymilvus import CollectionSchema, FieldSchema, DataType

    field_objects = []
    for f in fields:
        dtype = getattr(DataType, f["dtype"]) if isinstance(f["dtype"], str) else f["dtype"]
        kwargs: dict[str, Any] = {"name": f["name"], "dtype": dtype}
        if f.get("is_primary"):
            kwargs["is_primary"] = True
            kwargs["auto_id"] = f.get("auto_id", False)
        if "dim" in f:
            kwargs["dim"] = f["dim"]
        field_objects.append(FieldSchema(**kwargs))

    schema = CollectionSchema(fields=field_objects, description=description)
    coll = Collection(name=name, schema=schema)

    # 创建 IVF_FLAT 索引
    index_params = {
        "metric_type": "IP",  # Inner Product (cosine 需归一化)
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128},
    }
    coll.create_index(field_name="vector", index_params=index_params)
    coll.load()
    logger.info(f"Milvus collection '{name}' created")
    return coll
