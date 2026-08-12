"""调试接口 — 召回过程追踪（仅供开发调试，运维入口见 scripts/）。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.aitc.retrieval.case.service import debug_recall

router = APIRouter(prefix="/retrieval", tags=["检索调试"])


@router.get("/debug/case", summary="调试：用例混合召回全过程追踪")
async def debug_case_retrieve(
    query: str = Query(..., description="查询文本"),
    project_id: int | None = Query(None, description="项目 ID 过滤"),
    suite_id: int | None = Query(None, description="套件 ID 过滤"),
    top_k: int = Query(5, ge=1, le=20, description="返回数量"),
    db: AsyncSession = Depends(get_db),
):
    """返回向量、BM25、融合三阶段的完整结果和耗时，用于召回质量分析和参数调优。"""
    return await debug_recall(
        db=db,
        query=query,
        project_id=project_id,
        suite_id=suite_id,
        top_k=top_k,
    )
