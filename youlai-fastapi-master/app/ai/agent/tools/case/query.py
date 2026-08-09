"""用例域查询工具 — 5 个只读工具，包装 CaseService。

工具函数接收 ToolContext + Pydantic 参数，返回 JSON 字符串。
模型根据 description 自主选择调用哪个工具。
"""

import json
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.ai.agent.tools.base import ToolContext
from app.ai.agent.skills.case.tools import (
    _get_case_detail as _db_get_case_detail,
    _get_suite_tree as _db_get_suite_tree,
    _search_cases as _db_search_cases,
    _count_cases_in_suite,
    _get_project_name,
    _get_suite_name,
    _get_cases_by_suite,
)
from app.aitc.models import AiTcProject, AiTcCase
from sqlalchemy import select, func


# ═══════════════ Pydantic 参数模型 ═══════════════


class ListProjectsArgs(BaseModel):
    """无需参数，返回所有项目列表。"""
    pass


class GetSuiteTreeArgs(BaseModel):
    project_id: int = Field(..., description="项目 ID")


class SearchCasesArgs(BaseModel):
    suite_id: int | None = Field(None, description="套件 ID（模块 ID），不传则用当前页面的模块")
    keywords: str | None = Field(None, description="搜索关键字，在用例名称中模糊匹配")
    is_core: bool | None = Field(None, description="筛选核心用例：true=核心, false=非核心")
    has_steps: bool | None = Field(None, description="按步骤筛：true=有步骤, false=缺步骤")
    page: int = Field(1, description="页码，从 1 开始")
    page_size: int = Field(20, description="每页条数，最多 50")


class GetCaseDetailArgs(BaseModel):
    case_id: int = Field(..., description="用例 ID")


class GetSuiteSamplesArgs(BaseModel):
    suite_id: int | None = Field(None, description="套件 ID，不传则用当前页面模块")


# ═══════════════ 工具工厂函数 ═══════════════


def _case_to_dict(case: AiTcCase) -> dict[str, Any]:
    """将 ORM 对象转为模型友好的精简 dict。"""
    return {
        "id": case.id,
        "name": case.name,
        "purpose": case.purpose or "",
        "summary": (case.summary or "")[:200],
        "preconditions": (case.preconditions or "")[:100],
        "importance": case.importance,
        "is_core": case.is_core,
        "has_steps": bool(case.steps),
        "steps_count": len(case.steps) if case.steps else 0,
        "suite_id": case.suite_id,
        "project_id": case.project_id,
    }


def make_list_projects_tool(ctx: ToolContext) -> StructuredTool:
    """获取项目列表。"""

    async def run(**kwargs) -> str:
        result = await ctx.db.execute(
            select(AiTcProject.id, AiTcProject.name)
            .where(AiTcProject.is_deleted == 0)
            .order_by(AiTcProject.id)
        )
        projects = [{"id": r[0], "name": r[1]} for r in result]
        return json.dumps({"success": True, "projects": projects}, ensure_ascii=False)

    return StructuredTool(
        name="list_projects",
        description="获取所有可用项目列表。当用户想了解有哪些项目、需要选择项目时调用。",
        coroutine=run,
        args_schema=ListProjectsArgs,
    )


def make_get_suite_tree_tool(ctx: ToolContext) -> StructuredTool:
    """获取项目下的模块树。"""

    async def run(project_id: int, **kwargs) -> str:
        suites = await _db_get_suite_tree(ctx.db, project_id)
        tree = [{"id": s.id, "name": s.name, "parent_id": s.parent_id, "tree_path": s.tree_path, "description": s.description or ""} for s in suites]
        return json.dumps({"success": True, "suites": tree, "total": len(tree)}, ensure_ascii=False)

    return StructuredTool(
        name="get_suite_tree",
        description="获取指定项目下的模块（套件）树结构。当用户想了解项目有哪些模块时调用。",
        coroutine=run,
        args_schema=GetSuiteTreeArgs,
    )


def make_search_cases_tool(ctx: ToolContext) -> StructuredTool:
    """搜索用例列表（带过滤和分页）。"""

    async def run(
        suite_id: int | None = None,
        keywords: str | None = None,
        is_core: bool | None = None,
        has_steps: bool | None = None,
        page: int = 1,
        page_size: int = 20,
        **kwargs,
    ) -> str:
        suite_id = suite_id or ctx.suite_id
        if page_size > 50:
            page_size = 50

        conditions = [AiTcCase.is_deleted == 0]

        if suite_id:
            conditions.append(AiTcCase.suite_id == int(suite_id))

        if keywords:
            conditions.append(AiTcCase.name.ilike(f"%{keywords}%"))
        if is_core is not None:
            conditions.append(AiTcCase.is_core == (1 if is_core else 0))
        if has_steps is True:
            conditions.append(AiTcCase.steps != None)
        elif has_steps is False:
            conditions.append(AiTcCase.steps == None)

        # 总数
        count_q = select(func.count(AiTcCase.id)).where(*conditions)
        total = (await ctx.db.execute(count_q)).scalar() or 0

        # 分页数据
        offset = (page - 1) * page_size
        query = select(AiTcCase).where(*conditions).order_by(AiTcCase.id).offset(offset).limit(page_size)
        rows = (await ctx.db.execute(query)).scalars().all()

        cases = [_case_to_dict(c) for c in rows]

        return json.dumps({
            "success": True,
            "total": total,
            "page": page,
            "page_size": page_size,
            "cases": cases,
        }, ensure_ascii=False)

    return StructuredTool(
        name="search_cases",
        description=(
            "搜索/列出测试用例，支持按模块、关键字、是否核心用例、是否有步骤等条件过滤。"
            "当用户想查看某个模块有哪些用例、查找特定用例、了解用例概况时调用。"
            "has_steps=false 可找出缺少测试步骤的用例（需要补写步骤）。"
        ),
        coroutine=run,
        args_schema=SearchCasesArgs,
    )


def make_get_case_detail_tool(ctx: ToolContext) -> StructuredTool:
    """获取用例详情。"""

    async def run(case_id: int, **kwargs) -> str:
        case = await _db_get_case_detail(ctx.db, case_id)
        if case is None:
            return json.dumps({"success": False, "error": f"用例 ID={case_id} 不存在"}, ensure_ascii=False)

        detail = {
            "id": case.id,
            "name": case.name,
            "summary": case.summary or "",
            "preconditions": case.preconditions or "",
            "topo": case.topo or "",
            "test_data": case.test_data or "",
            "importance": case.importance,
            "is_core": case.is_core == 1,
            "purpose": case.purpose or "",
            "steps": case.steps or [],
            "suite_id": case.suite_id,
            "project_id": case.project_id,
        }
        return json.dumps({"success": True, "case": detail}, ensure_ascii=False)

    return StructuredTool(
        name="get_case_detail",
        description="获取单条测试用例的详细信息，包括步骤、前置条件、测试数据等。当用户想深入了解某条用例时调用。",
        coroutine=run,
        args_schema=GetCaseDetailArgs,
    )


def make_get_suite_samples_tool(ctx: ToolContext) -> StructuredTool:
    """获取模块下的样本用例。"""

    async def run(suite_id: int | None = None, **kwargs) -> str:
        suite_id = suite_id or ctx.suite_id
        if not suite_id:
            return json.dumps({"success": False, "error": "请指定模块 ID"}, ensure_ascii=False)

        result = await ctx.db.execute(
            select(AiTcCase)
            .where(
                AiTcCase.suite_id == int(suite_id),
                AiTcCase.is_sample == 1,
                AiTcCase.is_deleted == 0,
            )
            .limit(5)
        )
        samples = [_case_to_dict(c) for c in result.scalars().all()]

        return json.dumps({
            "success": True,
            "samples": samples,
            "total": len(samples),
        }, ensure_ascii=False)

    return StructuredTool(
        name="get_suite_samples",
        description="获取指定模块下标记为样本的用例列表。样本用例代表了该模块的用例编写规范。",
        coroutine=run,
        args_schema=GetSuiteSamplesArgs,
    )
