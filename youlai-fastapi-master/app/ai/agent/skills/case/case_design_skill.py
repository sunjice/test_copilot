"""设计测试用例 Skill — 根据需求描述，AI 设计一条新的测试用例。

SYNC 模式：在对话内即时返回用例草稿。
"""

from app.ai.agent.skills.base import BaseSkill, SkillMode, SkillResult, skill_registry


class CaseDesignSkill(BaseSkill):
    name = "case_design"
    description = "根据需求描述或功能点，设计一条新的测试用例，包含标题、前置条件、测试步骤和预期结果。当用户说'设计用例'、'新增用例'、'写一条用例'、'创建用例'时触发。"
    domain = "case"
    mode = SkillMode.SYNC
    keywords = ["设计用例", "新增用例", "写用例", "创建用例", "编写用例", "设计测试", "设计一条"]

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "requirement": {"type": "string", "description": "需求描述或功能点说明"},
                "project_id": {"type": "integer", "description": "目标项目 ID"},
            },
            "required": ["requirement"],
        }

    async def execute(self, params: dict, context: dict) -> SkillResult:
        requirement = params.get("requirement") or ""
        project_id = params.get("project_id") or context.get("project_id")

        if not requirement:
            return SkillResult(
                success=False,
                msg_type="clarify_card",
                content="请描述你需要测试的功能点或需求，我来帮你设计测试用例。",
                error="缺少需求描述",
            )

        return SkillResult(
            success=True,
            msg_type="confirm_card",
            content=f"根据需求「{requirement}」设计测试用例，等待确认后继续执行。",
            metadata={"requirement": requirement, "project_id": project_id},
        )


case_design_skill = CaseDesignSkill()
skill_registry.register(case_design_skill)
