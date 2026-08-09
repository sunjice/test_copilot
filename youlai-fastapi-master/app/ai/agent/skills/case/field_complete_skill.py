"""补全用例字段 Skill — 对指定模块下字段不完整的用例进行 AI 补全。

ASYNC 模式：返回确认卡片，用户确认后创建后台批量任务。
"""

from app.ai.agent.skills.base import BaseSkill, SkillMode, SkillResult, skill_registry
from app.ai.agent.skills.case.tools import (
    _count_cases_in_suite, _get_project_name, _get_suite_name, resolve_scope,
)
from app.aitc.constants import TaskType


class FieldCompleteSkill(BaseSkill):
    name = "case_complete"
    description = "参考同模块样本用例，对指定模块下字段不完整的用例进行 AI 补全（含测试步骤），或对用户指定的用例进行补全。当用户说'补全字段'、'完善用例'、'补充字段'时触发。"
    domain = "case"
    mode = SkillMode.ASYNC
    keywords = ["补全", "补充", "完善", "填充", "补写", "缺少", "完整", "缺字段", "信息不全"]
    required_page = "case"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目 ID"},
                "suite_id": {"type": "integer", "description": "模块 ID"},
                "case_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "要补全的用例 ID 列表，由 LLM 根据用户语义决定（可先调 search_cases 筛选）。不传则按 scope 解析。",
                },
            },
            "required": ["project_id", "suite_id"],
        }

    async def execute(self, params: dict, context: dict) -> SkillResult:
        project_id = params.get("project_id") or context.get("project_id")
        suite_id = params.get("suite_id") or context.get("suite_id")
        case_ids = params.get("case_ids")  # LLM 传入的目标用例 ID
        scope = params.get("scope")  # "all" | "selected" | None（case_ids 未传时使用）
        context_json = context.get("context_json", {})
        raw_selected_case_ids = context_json.get("selected_case_ids", []) if context_json else []
        raw_current_case_id = context_json.get("current_case_id") if context_json else None
        db = context.get("db_session")

        if not project_id or not suite_id:
            return SkillResult(
                success=False,
                msg_type="clarify_card",
                content="请先选择项目和模块。",
                error="缺少 project_id 或 suite_id",
            )

        total = await _count_cases_in_suite(db, int(suite_id))

        if total == 0:
            return SkillResult(
                success=False,
                content="所选模块下没有用例。",
                error="用例数为 0",
            )

        # case_ids 优先：LLM 已决定范围 → 直接用；否则回退到 scope 解析
        if case_ids:
            target_case_ids = [int(cid) for cid in case_ids]
        elif scope == "all":
            target_case_ids = None  # None = 模块全部用例，由 task 侧处理
        else:
            target_case_ids = await resolve_scope(
                db, int(suite_id), raw_selected_case_ids, raw_current_case_id,
            )

        scope_total = len(target_case_ids) if target_case_ids else total

        project_name = await _get_project_name(db, int(project_id))
        suite_name = await _get_suite_name(db, int(suite_id))
        task_type_label = TaskType.labels().get(TaskType.CASE_COMPLETE, "补全用例字段")

        scope_desc = (
            f"当前模块全部 {scope_total} 条"
            if target_case_ids is None
            else f"{'指定的' if case_ids else '已选中的'} {scope_total} 条"
        )

        case_list_preview = ""
        if target_case_ids:
            case_list_preview = "\n".join(
                f"- ID {cid}" for cid in target_case_ids[:10]
            )
            if len(target_case_ids) > 10:
                case_list_preview += f"\n- ... 等共 {scope_total} 条"

        content = (
            f"即将创建**{task_type_label}**任务，将对{scope_desc}用例"
            f"逐条参考样本用例补全字段（测试思想、前置条件、测试数据、拓扑、测试步骤），请确认以下信息：\n\n"
            f"| 项目 | {project_name} |\n"
            f"| 模块 | {suite_name} |\n"
            f"| 任务类型 | {task_type_label} |\n"
            f"| 用例数量 | {scope_total} 条 |\n"
        )
        if case_list_preview:
            content += f"\n涉及用例：\n{case_list_preview}"

        return SkillResult(
            success=True,
            msg_type="confirm_card",
            content=content,
            metadata={
                "skill_name": self.name,
                "task_type": TaskType.CASE_COMPLETE.value,
                "project_id": int(project_id),
                "suite_id": int(suite_id),
                "case_ids": target_case_ids,
                "project_name": project_name,
                "suite_name": suite_name,
                "total": scope_total,
            },
        )


field_complete_skill = FieldCompleteSkill()
skill_registry.register(field_complete_skill)
