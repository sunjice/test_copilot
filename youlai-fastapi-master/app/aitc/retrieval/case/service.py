"""用例召回的 Tool 入口 + 调试召回接口。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.aitc.retrieval.case.retriever import retrieve_similar_cases
from app.aitc.retrieval.common.schemas import SimilarCaseResult, DebugTrace


async def recall_similar_cases(
    db: AsyncSession,
    query: str,
    project_id: int | None = None,
    suite_id: int | None = None,
    importance: str | None = None,
    top_k: int = 5,
    enable_rerank: bool = False,
) -> list[dict]:
    """语义 + BM25 混合召回相似用例（供 Tool 调用，返回 dict 列表）。

    LLM 根据返回的 score / vector_score / bm25_score 判断相似度。
    """
    results, _ = await retrieve_similar_cases(
        db=db,
        query=query,
        project_id=project_id,
        suite_id=suite_id,
        importance=importance,
        top_k=top_k,
        enable_rerank=enable_rerank,
        debug=False,
    )
    return [r.model_dump() for r in results]


async def debug_recall(
    db: AsyncSession,
    query: str,
    project_id: int | None = None,
    suite_id: int | None = None,
    top_k: int = 5,
) -> dict:
    """调试召回（返回完整追踪信息，供 HTTP Debug 接口使用）。"""
    results, trace = await retrieve_similar_cases(
        db=db,
        query=query,
        project_id=project_id,
        suite_id=suite_id,
        top_k=top_k,
        debug=True,
    )
    return {
        "query": query,
        "results": [r.model_dump() for r in results],
        "total": len(results),
        "trace": trace.model_dump() if trace else None,
    }
