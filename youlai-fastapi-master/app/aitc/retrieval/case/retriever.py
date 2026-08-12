"""用例混合召回 — Milvus 向量 + ES BM25 + RRF 融合。"""

import asyncio
import time
import uuid
from typing import Any

from elasticsearch import AsyncElasticsearch
from loguru import logger
from pymilvus import Collection
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.aitc.case.models import AiTcCase
from app.aitc.retrieval.case.indexer import _ensure_es_index, _ensure_milvus_collection
from app.aitc.retrieval.common.cleaner import build_vector_text, steps_to_text
from app.aitc.retrieval.common.client import embed_texts, get_es_client
from app.aitc.retrieval.common.config import DEFAULT_TOP_K, ES_INDEX_CASE
from app.aitc.retrieval.common.fusion import rrf_fusion
from app.aitc.retrieval.common.schemas import DebugTrace, HitResult, SimilarCaseResult, StageDetail


def _build_es_query(query: str, filters: dict) -> dict:
    """构建 ES BM25 查询 DSL。"""
    must = [
        {
            "multi_match": {
                "query": query,
                "fields": [
                    "name_words^3",
                    "purpose^2",
                    "summary^2",
                    "steps_text",
                    "topo",
                ],
                "type": "best_fields",
            }
        }
    ]

    # 过滤条件
    filters_list = [{"term": {"is_deleted": False}}]
    if "project_id" in filters:
        filters_list.append({"term": {"project_id": filters["project_id"]}})
    if "suite_id" in filters:
        filters_list.append({"term": {"suite_id": filters["suite_id"]}})

    return {
        "query": {
            "bool": {
                "must": must,
                "filter": filters_list,
            }
        },
        "size": DEFAULT_TOP_K,
    }


def _build_milvus_expr(filters: dict) -> str:
    """构建 Milvus 过滤表达式。"""
    parts = ["is_deleted == false"]
    if "project_id" in filters:
        parts.append(f'project_id == {filters["project_id"]}')
    if "suite_id" in filters:
        parts.append(f'suite_id == {filters["suite_id"]}')
    return " && ".join(parts)


async def _query_vector(query: str, filters: dict) -> tuple[list[tuple[int, float, int]], float]:
    """Milvus 向量检索。

    Returns:
        ([(case_id, score, rank), ...], latency_ms)
    """
    t0 = time.perf_counter()

    vectors = await asyncio.get_event_loop().run_in_executor(None, embed_texts, [query])
    query_vector = vectors[0]

    coll = _ensure_milvus_collection()
    expr = _build_milvus_expr(filters)

    import numpy as np
    search_params = {"metric_type": "IP", "params": {"nprobe": 16}}
    results = coll.search(
        data=[np.array(query_vector, dtype=np.float32)],
        anns_field="vector",
        param=search_params,
        limit=DEFAULT_TOP_K,
        expr=expr,
        output_fields=["case_id"],
    )

    latency = (time.perf_counter() - t0) * 1000
    hits: list[tuple[int, float, int]] = []
    for i, hit in enumerate(results[0]):
        hits.append((hit.entity.get("case_id"), hit.score, i + 1))

    logger.debug(f"[retrieve] vector: {len(hits)} hits, {latency:.1f}ms")
    return hits, latency


async def _query_bm25(query: str, filters: dict) -> tuple[list[tuple[int, float, int]], float]:
    """ES BM25 关键词检索。

    Returns:
        ([(case_id, score, rank), ...], latency_ms)
    """
    t0 = time.perf_counter()
    es = await get_es_client()

    body = _build_es_query(query, filters)
    resp = await es.search(index=ES_INDEX_CASE, body=body)

    latency = (time.perf_counter() - t0) * 1000
    hits: list[tuple[int, float, int]] = []
    for i, hit in enumerate(resp["hits"]["hits"]):
        case_id = int(hit["_id"])
        hits.append((case_id, hit["_score"] or 0.0, i + 1))

    logger.debug(f"[retrieve] bm25: {len(hits)} hits, {latency:.1f}ms")
    return hits, latency


async def _batch_fetch_from_pg(db: AsyncSession, case_ids: list[int]) -> dict[int, AiTcCase]:
    """批量从 PG 回查用例详情。"""
    if not case_ids:
        return {}

    result = await db.execute(
        select(AiTcCase).where(
            AiTcCase.id.in_(case_ids),
            AiTcCase.is_deleted == 0,
        )
    )
    return {case.id: case for case in result.scalars().all()}


def _case_to_result(case: AiTcCase, fusion_item: dict) -> SimilarCaseResult:
    """ORM + 融合分数 → 返回对象。"""
    return SimilarCaseResult(
        case_id=case.id,
        name=case.name or "",
        purpose=case.purpose or "",
        summary=case.summary or "",
        steps=case.steps or [],
        topo=case.topo or "",
        importance=case.importance or 2,
        project_id=case.project_id,
        suite_id=case.suite_id,
        score=fusion_item.get("rrf_score", 0.0),
        vector_score=fusion_item.get("vector_score"),
        bm25_score=fusion_item.get("bm25_score"),
        rank_vector=fusion_item.get("rank_vector"),
        rank_bm25=fusion_item.get("rank_bm25"),
    )


async def retrieve_similar_cases(
    db: AsyncSession,
    query: str,
    project_id: int | None = None,
    suite_id: int | None = None,
    importance: str | None = None,
    top_k: int = 5,
    enable_rerank: bool = False,
    debug: bool = False,
) -> tuple[list[SimilarCaseResult], DebugTrace | None]:
    """混合召回主流程。

    Args:
        db: 数据库 session
        query: 自然语言查询
        project_id / suite_id / importance: 过滤条件
        top_k: 返回数量
        enable_rerank: 是否启用 reranker
        debug: 是否返回完整追踪信息

    Returns:
        (结果列表, 调试追踪 or None)
    """
    trace_id = uuid.uuid4().hex[:12]
    total_t0 = time.perf_counter()

    filters: dict[str, Any] = {}
    if project_id is not None:
        filters["project_id"] = project_id
    if suite_id is not None:
        filters["suite_id"] = suite_id

    debug_trace = None
    if debug:
        debug_trace = DebugTrace(trace_id=trace_id, query=query)

    # 确保索引存在
    await _ensure_es_index()

    # ── 并行双路召回 ──
    vector_future = _query_vector(query, filters)
    bm25_future = _query_bm25(query, filters)

    (vector_hits, vector_latency), (bm25_hits, bm25_latency) = await asyncio.gather(
        vector_future, bm25_future
    )

    # ── RRF 融合 ──
    fusion_t0 = time.perf_counter()
    fused = rrf_fusion(vector_hits, bm25_hits, top_k=top_k)
    fusion_latency = (time.perf_counter() - fusion_t0) * 1000

    # ── 可选 Reranker ──
    rerank_latency = 0.0
    if enable_rerank:
        # TODO: 接入 reranker
        logger.info(f"[retrieve] reranker not implemented, skipped")
        pass

    # ── 回查 PG ──
    pg_t0 = time.perf_counter()
    case_ids = [item["case_id"] for item in fused]
    case_map = await _batch_fetch_from_pg(db, case_ids)
    pg_latency = (time.perf_counter() - pg_t0) * 1000

    # ── 组装结果（保持融合排名顺序）──
    results = []
    for item in fused:
        case = case_map.get(item["case_id"])
        if case is None:
            continue
        results.append(_case_to_result(case, item))

    total_latency = (time.perf_counter() - total_t0) * 1000
    logger.info(
        f"[retrieve] trace={trace_id} query='{query[:50]}' "
        f"results={len(results)} "
        f"latency_total={total_latency:.1f}ms "
        f"vector={vector_latency:.1f}ms({len(vector_hits)}) "
        f"bm25={bm25_latency:.1f}ms({len(bm25_hits)}) "
        f"fusion={fusion_latency:.1f}ms pg={pg_latency:.1f}ms"
    )

    # ── 调试追踪 ──
    if debug and debug_trace:
        debug_trace.stages["vector"] = StageDetail(
            results=[HitResult(case_id=cid, score=round(s, 4), rank=r) for cid, s, r in vector_hits],
            total=len(vector_hits),
            latency_ms=round(vector_latency, 2),
        )
        debug_trace.stages["bm25"] = StageDetail(
            results=[HitResult(case_id=cid, score=round(s, 4), rank=r) for cid, s, r in bm25_hits],
            total=len(bm25_hits),
            latency_ms=round(bm25_latency, 2),
        )
        debug_trace.stages["fusion"] = StageDetail(
            results=[HitResult(case_id=item["case_id"], score=item["rrf_score"], rank=i + 1) for i, item in enumerate(fused)],
            total=len(fused),
            latency_ms=round(fusion_latency, 2),
        )
        if enable_rerank:
            debug_trace.stages["rerank"] = StageDetail(total=0, latency_ms=round(rerank_latency, 2))
        debug_trace.stages["pg_fetch"] = StageDetail(total=len(case_map), latency_ms=round(pg_latency, 2))
        debug_trace.total_latency_ms = round(total_latency, 2)

    return results, debug_trace
