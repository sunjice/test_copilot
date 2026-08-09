"""用例域操作工具 — 6 个能力工具，直接复用现有 Skill.execute() 逻辑。

content_and_artifact 模式:
- 工具返回 (content_text, artifact_dict) 元组
- content_text → 给模型看（ToolMessage.content）
- artifact_dict → 给 UI 系统（ToolMessage.artifact），包含卡片数据
- 不再走 JSON 字符串解析
"""

import json
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.ai.agent.tools.base import ToolContext
from app.ai.agent.skills.base import SkillResult, skill_registry


# ═══════════════ Pydantic 参数模型 ═══════════════


class CreateTaskArgs(BaseModel):
    """创建异步任务（核心挑选/用例审核/脚本生成/字段补全）的通用参数。"""
    suite_id: int | None = Field(None, description="模块 ID，不传则用当前页面的模块")
    project_id: int | None = Field(None, description="项目 ID，不传则用当前页面的项目")
    scope: str | None = Field(None, description="操作范围：'all' 整个模块全部用例，'selected' 或留空则处理页面上选中的用例。仅在用户明确要操作整个模块时传 'all'")
    case_ids: list[int] | None = Field(None, description="指定要处理的用例 ID 列表（仅字段补全任务使用）。如果提供此参数，scope 将被忽略。可通过 search_cases 提前筛选出需要补全的用例再传入")


class CompleteStepsArgs(BaseModel):
    """补写测试步骤的参数。"""
    case_id: int | None = Field(None, description="用例 ID")
    case_title: str | None = Field(None, description="用例标题（当无 ID 时可用标题描述）")


class DesignCaseArgs(BaseModel):
    """设计测试用例的参数。"""
    requirement: str = Field(..., description="需求描述或功能点说明")


# ═══════════════ 内部工具 ═══════════════


def _build_skill_context(ctx: ToolContext) -> dict[str, Any]:
    """构建传给 Skill.execute() 的 context dict。"""
    return {
        "session_id": ctx.session_id,
        "project_id": ctx.project_id,
        "suite_id": ctx.suite_id,
        "domain": ctx.domain,
        "context_json": ctx.context_json,
        "db_session": ctx.db,
    }


async def _run_skill(skill_name: str, params: dict, ctx: ToolContext) -> tuple[str, dict | None]:
    """执行一个 Skill，返回 (content_text, artifact_dict) 元组。

    content_text  → 给模型看的摘要文本
    artifact_dict → 给 UI 渲染的卡片数据（draft_card / confirm_card），无卡片时为 None
    """
    skill = skill_registry.get(skill_name)
    if skill is None:
        return (f"Skill '{skill_name}' 未注册", None)

    result: SkillResult = await skill.execute(params, _build_skill_context(ctx))
    return _result_to_tuple(result, skill_name)


def _result_to_tuple(result: SkillResult, skill_name: str) -> tuple[str, dict | None]:
    """将 SkillResult 转为 (content, artifact) 元组。

    - content: 给模型的简短文本描述
    - artifact: 卡片数据字典（draft_card/confirm_card），无卡片时为 None
    """
    if not result.success:
        return (result.error or result.content or f"{skill_name} 执行失败", None)

    # 有卡片类型 → 提取为 artifact
    if result.msg_type in ("draft_card", "confirm_card"):
        artifact = {
            "msg_type": result.msg_type,
            "content": result.content or "",
            "draft_type": result.draft_type,
            "draft_data": result.draft_data,
            "metadata": result.metadata,
        }
        content = result.content or f"已生成 {skill_name} 结果，请确认。"
        return (content, artifact)

    # 无卡片 → 纯文本，artifact 为 None
    return (result.content or f"{skill_name} 执行完成", None)


# ═══════════════ 工具工厂函数 ═══════════════


def make_create_core_select_task_tool(ctx: ToolContext) -> StructuredTool:
    """挑选核心用例任务。"""

    async def run(suite_id: int | None = None, project_id: int | None = None, **kwargs) -> tuple[str, dict | None]:
        params = {
            "suite_id": suite_id or ctx.suite_id,
            "project_id": project_id or ctx.project_id,
        }
        return await _run_skill("core_select", params, ctx)

    return StructuredTool(
        name="create_core_select_task",
        description=(
            "从指定模块的用例中挑选核心/重要用例，返回确认卡片等用户确认后创建后台任务。"
            "当用户说'挑选核心用例'、'挑重要用例'、'哪些用例是核心的'时调用。"
        ),
        coroutine=run,
        args_schema=CreateTaskArgs,
        response_format="content_and_artifact",
    )


def make_create_case_review_task_tool(ctx: ToolContext) -> StructuredTool:
    """用例审核任务。"""

    async def run(suite_id: int | None = None, project_id: int | None = None, scope: str | None = None, **kwargs) -> tuple[str, dict | None]:
        params = {
            "suite_id": suite_id or ctx.suite_id,
            "project_id": project_id or ctx.project_id,
            "scope": scope,
        }
        return await _run_skill("case_review", params, ctx)

    return StructuredTool(
        name="create_case_review_task",
        description=(
            "审核指定模块下测试用例的质量，检查字段完整性、步骤规范性等。返回确认卡片等用户确认。"
            "当用户说'审核用例'、'检查用例质量'、'评审用例'、'用例写得怎么样'时调用。"
            "scope 参数：用户明确要求审核'整个模块'、'全部用例'时传 'all'；"
            "要求审核'选中的'、'这些'时传 'selected'；未明确指定时不传。"
        ),
        coroutine=run,
        args_schema=CreateTaskArgs,
        response_format="content_and_artifact",
    )


def make_create_script_gen_task_tool(ctx: ToolContext) -> StructuredTool:
    """脚本生成任务。"""

    async def run(suite_id: int | None = None, project_id: int | None = None, **kwargs) -> tuple[str, dict | None]:
        params = {
            "suite_id": suite_id or ctx.suite_id,
            "project_id": project_id or ctx.project_id,
        }
        return await _run_skill("script_gen", params, ctx)

    return StructuredTool(
        name="create_script_gen_task",
        description=(
            "为指定模块下的测试用例生成 pytest 自动化测试脚本。返回确认卡片等用户确认。"
            "当用户说'生成脚本'、'写自动化脚本'、'生成自动化测试'、'给我写个pytest脚本'时调用。"
        ),
        coroutine=run,
        args_schema=CreateTaskArgs,
        response_format="content_and_artifact",
    )


def make_create_case_complete_task_tool(ctx: ToolContext) -> StructuredTool:
    """补全用例字段任务。"""

    async def run(suite_id: int | None = None, project_id: int | None = None, scope: str | None = None, case_ids: list[int] | None = None, **kwargs) -> tuple[str, dict | None]:
        params = {
            "suite_id": suite_id or ctx.suite_id,
            "project_id": project_id or ctx.project_id,
            "scope": scope,
            "case_ids": case_ids,
        }
        return await _run_skill("field_complete", params, ctx)

    return StructuredTool(
        name="create_case_complete_task",
        description=(
            "对指定模块下字段不完整的用例进行 AI 补全（含测试步骤），参考同模块样本用例的写法。"
            "返回确认卡片等用户确认后创建后台任务。"
            "用例必须有编号、名称、测试目的，缺任一项的用例将在执行阶段被跳过。"
            "当用户说'补全字段'、'完善用例'、'补充信息'、'帮忙补写'时调用。"
            "用户可能要补全选中的用例、或只补全字段不全的用例，根据语义自行判断处理范围：\n"
            "- 如果用户只要求补全「字段不全/缺步骤」的用例，可先调 search_cases(has_steps=false) 查出缺步骤的用例 ID，"
            "再通过 case_ids 参数指定只处理这些；\n"
            "- 如果用户要求处理「选中的这些」，scope 不传或传 'selected'；\n"
            "- 如果用户要求处理「整个模块」，scope 传 'all'。"
        ),
        coroutine=run,
        args_schema=CreateTaskArgs,
        response_format="content_and_artifact",
    )


def make_complete_steps_tool(ctx: ToolContext) -> StructuredTool:
    """补写测试步骤。"""

    async def run(case_id: int | None = None, case_title: str | None = None, **kwargs) -> tuple[str, dict | None]:
        params = {"case_id": case_id, "case_title": case_title}
        return await _run_skill("steps_complete", params, ctx)

    return StructuredTool(
        name="complete_case_steps",
        description=(
            "根据用例的标题和测试目的，AI 补写详细的测试步骤和预期结果。返回草稿卡片。"
            "当用户说'补写步骤'、'补充测试步骤'、'写步骤'、'这个用例没步骤帮我补一下'时调用。"
        ),
        coroutine=run,
        args_schema=CompleteStepsArgs,
        response_format="content_and_artifact",
    )


def make_design_case_tool(ctx: ToolContext) -> StructuredTool:
    """设计测试用例。"""

    async def run(requirement: str, **kwargs) -> tuple[str, dict | None]:
        params = {
            "requirement": requirement,
            "project_id": ctx.project_id,
        }
        return await _run_skill("case_design", params, ctx)

    return StructuredTool(
        name="design_test_case",
        description=(
            "根据需求描述，从零设计一条新的测试用例（包含标题、前置条件、测试步骤、预期结果）。返回草稿卡片。"
            "当用户说'设计一条用例'、'帮我写一条测试用例'、'根据这个需求设计用例'时调用。"
        ),
        coroutine=run,
        args_schema=DesignCaseArgs,
        response_format="content_and_artifact",
    )
