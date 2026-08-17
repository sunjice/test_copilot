"""用例域 — 上下文构造器。

自由对话模式下，将当前项目/模块/选中用例等信息注入 LLM system prompt。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.aitc.models import AiTcCase, AiTcSuite
from app.ai.chat.context_builder import BaseContextBuilder, context_builder_registry
from app.ai.agent.skills.case.tools import (
    _get_project_name,
    resolve_suite_ids,
    get_suite_names,
    count_cases_in_suites,
    _get_subtree_suite_ids,
)


class CaseContextBuilder(BaseContextBuilder):
    """用例管理页上下文构造器。"""

    domain = "case"

    async def build(self, context_json: dict, db: AsyncSession) -> str:
        project_id = context_json.get("project_id")
        selected_case_ids = context_json.get("selected_case_ids", [])

        parts: list[str] = []

        # 项目名
        if project_id:
            project_name = await _get_project_name(db, project_id)
            parts.append(f"- 项目: {project_name or f'ID:{project_id}'}")

        # 模块名 + 用例统计 + 用例列表（支持多模块）
        suite_ids = await resolve_suite_ids(
            db, context_json, context_json.get("suite_id")
        )
        if suite_ids:
            suite_names = await get_suite_names(db, suite_ids)
            total_count = await count_cases_in_suites(db, suite_ids)
            if len(suite_ids) == 1:
                parts.append(f"- 模块: {suite_names[0] or f'ID:{suite_ids[0]}'}（{total_count} 条用例）")
            else:
                names = "、".join(suite_names) if suite_names else str(suite_ids)
                parts.append(f"- 模块（{len(suite_ids)} 个）: {names}（共 {total_count} 条用例）")

            # 注入模块下（含子模块）所有用例的编号和名称（多模块时合并，总上限 200）
            cases: list[tuple[int, str]] = []
            for sid in suite_ids:
                if len(cases) >= 200:
                    break
                cases.extend(await self._get_case_list_in_suite(db, sid, limit=200 - len(cases)))
            if cases:
                lines = "\n".join(f"  - #{case_id}: {name}" for case_id, name in cases)
                parts.append(f"- 用例列表：\n{lines}")
                if total_count > len(cases):
                    parts.append(f"  （仅展示前 {len(cases)} 条）")

        # 当前选中用例概览
        if selected_case_ids:
            count = len(selected_case_ids)
            preview = await self._get_selected_case_names(db, selected_case_ids[:5])
            parts.append(f"- 当前选中 {count} 条用例" + (f"，例如: {preview}" if preview else ""))

        if not parts:
            return ""

        return "\n[当前页面上下文]\n" + "\n".join(parts) + "\n注意：如果用户有选中用例，可优先作为操作对象。但如果用户明确要求对整个模块操作，以用户意图为准。"

    @staticmethod
    async def _get_case_list_in_suite(
        db: AsyncSession, suite_id: int, limit: int = 200
    ) -> list[tuple[int, str]]:
        """获取模块及其子模块下的用例列表（编号+名称），按 ID 排序（parent_id 递归）。"""
        suite = await db.get(AiTcSuite, suite_id)
        if suite is None or suite.is_deleted:
            return []

        all_suite_ids = await _get_subtree_suite_ids(db, suite_id)

        result = await db.execute(
            select(AiTcCase.id, AiTcCase.name)
            .where(
                AiTcCase.suite_id.in_(all_suite_ids),
                AiTcCase.is_deleted == 0,
            )
            .order_by(AiTcCase.id)
            .limit(limit)
        )
        return [(row[0], row[1]) for row in result]

    @staticmethod
    async def _get_selected_case_names(db: AsyncSession, case_ids: list) -> str:
        result = await db.execute(
            select(AiTcCase.name).where(
                AiTcCase.id.in_(case_ids),
                AiTcCase.is_deleted == 0,
            )
        )
        names = [row[0] for row in result]
        return "、".join(names)


case_context_builder = CaseContextBuilder()
context_builder_registry.register(case_context_builder)
