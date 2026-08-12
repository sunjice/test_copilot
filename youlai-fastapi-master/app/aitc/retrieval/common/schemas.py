"""公共 Pydantic 模型 — 召回结果、调试追踪。"""

from pydantic import BaseModel, Field


class HitResult(BaseModel):
    """单路召回的命中项。"""
    case_id: int
    score: float
    rank: int


class StageDetail(BaseModel):
    """单阶段召回详情（向量 / BM25 / 融合 / 重排）。"""
    results: list[HitResult] = Field(default_factory=list)
    total: int = 0
    latency_ms: float = 0


class DebugTrace(BaseModel):
    """完整召回过程追踪。"""
    trace_id: str
    query: str
    stages: dict[str, StageDetail] = Field(default_factory=dict)
    total_latency_ms: float = 0
    error: str | None = None


class SimilarCaseResult(BaseModel):
    """recall_similar_cases 返回的单条结果。"""
    case_id: int
    name: str
    purpose: str = ""
    summary: str = ""
    steps: list = Field(default_factory=list)
    topo: str = ""
    importance: int = 2
    project_id: int = 0
    suite_id: int = 0
    score: float = 0.0
    vector_score: float | None = None
    bm25_score: float | None = None
    rank_vector: int | None = None
    rank_bm25: int | None = None


class RetrieveRequest(BaseModel):
    """召回请求参数。"""
    query: str
    project_id: int | None = None
    suite_id: int | None = None
    importance: str | None = None
    top_k: int = 5
    enable_rerank: bool = False


class RetrieveResponse(BaseModel):
    """召回响应。"""
    success: bool = True
    results: list[SimilarCaseResult] = Field(default_factory=list)
    total: int = 0
    debug: DebugTrace | None = None
