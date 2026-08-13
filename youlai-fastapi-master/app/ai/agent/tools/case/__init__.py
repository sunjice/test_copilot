"""用例域工具注册表 — 汇总查询和操作工具，提供统一的构建入口。"""

from langchain_core.tools import BaseTool
from pydantic import BaseModel

from app.ai.agent.tools.base import ToolContext, tool_registry
from app.ai.agent.tools.case.query import (
    make_list_projects_tool,
    make_get_suite_tree_tool,
    make_search_cases_tool,
    make_get_case_detail_tool,
    make_get_suite_samples_tool,
)
from app.ai.agent.tools.case.recall import (
    make_recall_similar_cases_tool,
)
from app.ai.agent.tools.case.action import (
    make_create_core_select_task_tool,
    make_create_case_review_task_tool,
    make_create_script_gen_task_tool,
    make_create_case_complete_task_tool,
    make_design_case_tool,
)
from app.ai.agent.tools.case.clarify import build_clarify_tools


def build_case_tools(ctx: ToolContext) -> list[BaseTool]:
    """构建用例域的所有 agent 工具。

    每个请求调用一次，工具实例携带当前请求的 ToolContext（db session 等）。
    """
    return [
        # ── 查询类 ──
        make_list_projects_tool(ctx),
        make_get_suite_tree_tool(ctx),
        make_search_cases_tool(ctx),
        make_get_case_detail_tool(ctx),
        make_get_suite_samples_tool(ctx),
        make_recall_similar_cases_tool(ctx),
        # ── 澄清类 ──
        *build_clarify_tools(ctx),
        # ── 操作类 ──
        make_create_core_select_task_tool(ctx),
        make_create_case_review_task_tool(ctx),
        make_create_script_gen_task_tool(ctx),
        make_create_case_complete_task_tool(ctx),
        make_design_case_tool(ctx),
    ]


# ── 工具名称分类映射，用于自动生成 prompt 的工具箱章节 ──
_QUERY_TOOLS = {"list_projects", "get_suite_tree", "search_cases", "get_case_detail", "get_suite_samples", "recall_similar_cases"}
_CLARIFY_TOOLS = {"ask_question"}
_TASK_TOOLS = {"create_core_select_task", "create_case_review_task", "create_script_gen_task", "create_case_complete_task"}
_INSTANT_TOOLS = {"design_test_case"}


def generate_tools_prompt(tools: list[BaseTool]) -> str:
    """从工具列表动态生成「工具箱」prompt 片段。

    所有工具的描述、参数信息均从代码中的 StructuredTool 元数据自动提取，
    不再需要手动在 agent_case.txt 中维护工具清单，彻底消除漂移风险。
    """
    sections: dict[str, list[str]] = {
        "查询": [],
        "澄清": [],
        "操作": [],
        "即时处理": [],
    }

    for tool in tools:
        name = tool.name
        desc = tool.description or ""

        # 提取参数信息
        param_str = _format_params(tool)
        entry = f"- `{name}`{param_str} — {desc}"

        if name in _QUERY_TOOLS:
            sections["查询"].append(entry)
        elif name in _CLARIFY_TOOLS:
            sections["澄清"].append(entry)
        elif name in _TASK_TOOLS:
            sections["操作"].append(entry)
        else:
            sections["即时处理"].append(entry)

    lines = ["## 你的工具箱", ""]

    if sections["查询"]:
        lines.append("### 查询类工具（随时可用，只读安全）")
        lines.extend(sections["查询"])
        lines.append("")

    if sections["澄清"]:
        lines.append("### 澄清类工具（向用户提问，收集信息）")
        lines.extend(sections["澄清"])
        lines.append("")

    if sections["操作"]:
        lines.append("### 任务类工具（发起批量处理，返回确认卡片等用户确认）")
        lines.extend(sections["操作"])
        lines.append("")

    if sections["即时处理"]:
        lines.append("### 即时处理工具（返回确认卡片或即时结果）")
        lines.extend(sections["即时处理"])
        lines.append("")

    return "\n".join(lines)


def _format_params(tool: BaseTool) -> str:
    """从工具的 args_schema 提取参数签名，如 (project_id: 必填, suite_id: 可选)。"""
    if not hasattr(tool, "args_schema") or tool.args_schema is None:
        return ""

    args_schema = tool.args_schema
    if not issubclass(args_schema, BaseModel):
        return ""

    fields = args_schema.model_fields
    if not fields:
        return ""

    parts: list[str] = []
    for field_name, field_info in fields.items():
        is_required = field_info.is_required()
        tag = "必填" if is_required else "可选"
        parts.append(f"{field_name}: {tag}")

    return f" ({', '.join(parts)})" if parts else ""


# 注册用例域工具构造器
tool_registry.register("case", build_case_tools)
