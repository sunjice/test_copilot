"""核心用例挑选 Skill — 对指定模块下的用例，挑选核心用例。"""

from app.ai.agent.skills.base import BaseSkill, SkillMode, SkillResult, skill_registry
from app.ai.agent.skills.case.tools import (
    _get_project_name, resolve_scope,
    resolve_suite_ids, get_suite_names, count_cases_in_suites,
)
from app.aitc.constants import TaskType


class CoreSelectSkill(BaseSkill):
    name = "core_select"
    description = "从指定模块下挑选核心/重要的测试用例。当用户说'挑选核心用例'、'挑重要用例'、'核心用例'时触发。"
    domain = "case"
    mode = SkillMode.ASYNC
    keywords = ["核心用例", "重要用例", "挑选核心", "挑重要", "核心挑选", "core", "核心的用例"]
    required_page = "case"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目 ID"},
                "suite_id": {"type": "integer", "description": "模块 ID（必填，只处理该模块下的用例）"},
            },
            "required": ["project_id", "suite_id"],
        }

    async def execute(self, params: dict, context: dict) -> SkillResult:
        project_id = params.get("project_id") or context.get("project_id")
        context_json = context.get("context_json", {})
        raw_selected_case_ids = context_json.get("selected_case_ids", []) if context_json else []
        raw_current_case_id = context_json.get("current_case_id") if context_json else None
        db = context.get("db_session")

        if not project_id:
            return SkillResult(
                success=False,
                msg_type="clarify_card",
                content="请先在左侧选择一个项目。",
                error="缺少 project_id",
            )

        # 解析最终模块列表（支持多选，去子孙）
        suite_ids = await resolve_suite_ids(
            db, context_json,
            params.get("suite_id") or context.get("suite_id"),
        )
        if not suite_ids:
            return SkillResult(
                success=False,
                msg_type="clarify_card",
                content="请先在左侧模块树中选择要处理的模块（只对该模块下的用例执行）。",
                error="缺少 suite_id",
            )

        total = await count_cases_in_suites(db, suite_ids)

        if total == 0:
            return SkillResult(
                success=False,
                content="所选模块下没有用例，请先导入用例或选择其他模块。",
                error="用例数为 0",
            )

        # 防御校验 + 优先级裁决：current_case_id > selected_case_ids > 全模块
        # 多模块时，selected_case_ids 仍可跨模块命中，resolve_scope 按第一个模块校验
        target_case_ids = await resolve_scope(
            db, suite_ids[0], raw_selected_case_ids, raw_current_case_id,
        )
        scope_total = len(target_case_ids) if target_case_ids else total
        scope_desc = f"已选中的 {scope_total} 条" if target_case_ids else "所选模块下的"

        # 获取项目名和模块名，构建确认卡片
        project_name = await _get_project_name(db, int(project_id))
        suite_names = await get_suite_names(db, suite_ids)
        task_type_label = TaskType.labels().get(TaskType.CORE_SELECT, "挑选核心用例")

        suite_display = "、".join(suite_names) if suite_names else str(suite_ids)
        content = (
            f"即将创建**{task_type_label}**任务，将对{scope_desc}用例进行核心挑选，请确认以下信息：\n\n"
            f"| 项目 | {project_name} |\n"
            f"| 模块 | {suite_display}（共 {len(suite_ids)} 个，将分别创建任务） |\n"
            f"| 任务类型 | {task_type_label} |\n"
            f"| 用例数量 | {scope_total} 条 |\n"
        )

        return SkillResult(
            success=True,
            msg_type="confirm_card",
            content=content,
            metadata={
                "skill_name": self.name,
                "task_type": TaskType.CORE_SELECT.value,
                "project_id": int(project_id),
                "suite_ids": suite_ids,
                "suite_names": suite_names,
                "case_ids": target_case_ids,
                "project_name": project_name,
                "total": scope_total,
            },
        )


core_select_skill = CoreSelectSkill()
skill_registry.register(core_select_skill)