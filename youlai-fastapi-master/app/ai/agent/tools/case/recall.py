"""用例相似召回工具 — 语义向量 + BM25 混合检索。"""

import json

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.ai.agent.tools.base import ToolContext
from app.aitc.retrieval.case.service import recall_similar_cases as _recall


class RecallSimilarCasesArgs(BaseModel):
    """recall_similar_cases 参数。"""
    query: str = Field(..., description="自然语言查询描述，如 '用户登录接口测试'、'网络断开后重连' 等")
    project_id: int | None = Field(None, description="项目 ID 过滤，不传则全项目搜索")
    suite_id: int | None = Field(None, description="套件（模块） ID 过滤，不传则不按模块过滤")
    importance: str | None = Field(None, description="重要程度过滤：高/中/低")
    top_k: int = Field(5, description="返回数量，默认 5，最多 10")
    enable_rerank: bool = Field(False, description="是否启用 reranker 精排，默认关闭")


def make_recall_similar_cases_tool(ctx: ToolContext) -> StructuredTool:
    """构建 recall_similar_cases 工具。

    使用语义向量 + BM25 双路召回 → RRF 融合，查找最相似的测试用例。
    与 search_cases（PG 精确过滤）和 get_case_detail（按 ID 查询）职责不同。
    """

    async def run(
        query: str,
        project_id: int | None = None,
        suite_id: int | None = None,
        importance: str | None = None,
        top_k: int = 5,
        enable_rerank: bool = False,
        **kwargs,
    ) -> str:
        if top_k > 10:
            top_k = 10

        results = await _recall(
            db=ctx.db,
            query=query,
            project_id=project_id or ctx.project_id,
            suite_id=suite_id or ctx.suite_id,
            importance=importance,
            top_k=top_k,
            enable_rerank=enable_rerank,
        )

        return json.dumps({
            "success": True,
            "total": len(results),
            "results": results,
        }, ensure_ascii=False)

    return StructuredTool(
        name="recall_similar_cases",
        description=(
            "语义搜索相似测试用例。根据自然语言描述，使用 AI 语义理解 + BM25 关键词双路混合检索，"
            "查找与描述内容最相似的用例。适用场景：想找某个功能相关的所有测试用例、"
            "用户提供了测试场景描述需要匹配已有用例、查找相似测试思路等。"
            "注意：如需按用例 ID 精确查询用例详情，请用 get_case_detail；"
            "如需按模块/关键字/核心用例等条件过滤列表，请用 search_cases。"
        ),
        coroutine=run,
        args_schema=RecallSimilarCasesArgs,
    )
