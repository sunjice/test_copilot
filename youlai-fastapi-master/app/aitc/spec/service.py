"""规范域 — 业务逻辑层。"""

from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.exceptions import BusinessException
from app.pagination import PageResult
from app.response import ResultCode
from app.aitc.spec.models import AiTcSpec
from app.aitc.case.models import AiTcProject, AiTcSuite
from app.aitc.spec.schemas import (
    SpecCreate, SpecQuery, SpecUpdate, SpecVO,
)
from app.aitc.schemas import OptionVO
from app.aitc.constants import TaskType


class SpecService:
    """规范域全部业务逻辑。"""

    SPEC_TYPE_TITLES = {"general": "通用规范", "module_specific": "模块专用规范", "common_issues": "常见问题规范"}
    SPEC_TYPE_ORDER = ["general", "module_specific", "common_issues"]

    def __init__(self, db: AsyncSession):
        self.db = db

    # ═══════════════ 规范管理 CRUD ═══════════════

    async def get_spec_page(self, query: SpecQuery) -> PageResult:
        conditions = [AiTcSpec.is_deleted == 0]
        if query.projectId is not None:
            conditions.append(
                (AiTcSpec.project_id == query.projectId) | (AiTcSpec.project_id.is_(None))
            )
        if query.suiteId is not None:
            conditions.append(AiTcSpec.suite_id == query.suiteId)
        if query.taskType:
            conditions.append(AiTcSpec.task_type == query.taskType)
        if query.specType:
            conditions.append(AiTcSpec.spec_type == query.specType)
        if query.keywords:
            kw = f"%{query.keywords}%"
            conditions.append(AiTcSpec.content.ilike(kw))

        stmt = (
            select(AiTcSpec)
            .where(*conditions)
            .order_by(AiTcSpec.id)
        )
        count_q = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        offset = (query.pageNum - 1) * query.pageSize
        rows = await self.db.execute(stmt.offset(offset).limit(query.pageSize))
        items = rows.scalars().all()

        # 批量查项目名、套件名
        pids = [it.project_id for it in items if it.project_id]
        sids = [it.suite_id for it in items if it.suite_id]
        pname_map: dict[int, str] = {}
        sname_map: dict[int, str] = {}
        if pids:
            prows = await self.db.execute(
                select(AiTcProject.id, AiTcProject.name).where(AiTcProject.id.in_(pids))
            )
            pname_map = {r.id: r.name for r in prows}
        if sids:
            srows = await self.db.execute(
                select(AiTcSuite.id, AiTcSuite.name).where(AiTcSuite.id.in_(sids))
            )
            sname_map = {r.id: r.name for r in srows}

        return PageResult(
            records=[
                self._spec_to_vo(s, pname_map.get(s.project_id), sname_map.get(s.suite_id))
                for s in items
            ],
            total=total,
            pageNum=query.pageNum,
            pageSize=query.pageSize,
        )

    async def get_spec_by_id(self, spec_id: int) -> SpecVO:
        result = await self.db.execute(
            select(AiTcSpec).where(AiTcSpec.id == spec_id, AiTcSpec.is_deleted == 0)
        )
        s = result.scalar_one_or_none()
        if s is None:
            raise BusinessException(code=ResultCode.DATA_NOT_FOUND, msg="规范不存在")
        project_name, suite_name = await self._get_spec_relation_names(s)
        return self._spec_to_vo(s, project_name, suite_name)

    async def create_spec(self, form: SpecCreate) -> SpecVO:
        s = AiTcSpec(**form.model_dump())
        self.db.add(s)
        await self.db.flush()
        logger.info(f"Spec created: task={form.task_type} type={form.spec_type} id={s.id}")
        project_name, suite_name = await self._get_spec_relation_names(s)
        return self._spec_to_vo(s, project_name, suite_name)

    async def update_spec(self, form: SpecUpdate) -> SpecVO:
        result = await self.db.execute(
            select(AiTcSpec).where(AiTcSpec.id == form.id, AiTcSpec.is_deleted == 0)
        )
        s = result.scalar_one_or_none()
        if s is None:
            raise BusinessException(code=ResultCode.DATA_NOT_FOUND, msg="规范不存在")
        s.project_id = form.project_id
        s.suite_id = form.suite_id
        s.task_type = form.task_type
        s.spec_type = form.spec_type
        s.content = form.content
        s.sort_order = form.sort_order
        s.status = form.status
        s.update_time = datetime.now()
        await self.db.flush()
        project_name, suite_name = await self._get_spec_relation_names(s)
        return self._spec_to_vo(s, project_name, suite_name)

    async def delete_spec(self, ids: str) -> int:
        id_list = [int(x) for x in ids.split(",") if x.strip()]
        if not id_list:
            raise BusinessException(code=ResultCode.PARAM_VALID_FAIL, msg="请选择规范")
        await self.db.execute(
            text("UPDATE ai_tc_specs SET is_deleted = 1 WHERE id = ANY(:ids)"),
            {"ids": id_list},
        )
        return len(id_list)

    async def get_spec_options(
        self,
        project_id: int | None = None,
        task_type: str | None = None,
        spec_type: str | None = None,
    ) -> list[OptionVO]:
        """获取规范下拉选项。"""
        conditions = [AiTcSpec.is_deleted == 0, AiTcSpec.status == 1]
        if project_id is not None:
            conditions.append(
                (AiTcSpec.project_id == project_id) | (AiTcSpec.project_id.is_(None))
            )
        if task_type:
            conditions.append(AiTcSpec.task_type == task_type)
        if spec_type:
            conditions.append(AiTcSpec.spec_type == spec_type)
        rows = await self.db.execute(
            select(AiTcSpec.id, AiTcSpec.task_type, AiTcSpec.spec_type).where(*conditions)
        )
        return [
            OptionVO(
                value=r.id,
                label=f"[{TaskType.labels().get(r.task_type, r.task_type)}] {SpecType.labels().get(r.spec_type, r.spec_type)}",
            )
            for r in rows
        ]

    async def _get_spec_relation_names(self, s: AiTcSpec) -> tuple[str | None, str | None]:
        project_name = None
        suite_name = None
        if s.project_id:
            proj = await self.db.get(AiTcProject, s.project_id)
            if proj:
                project_name = proj.name
        if s.suite_id:
            suite = await self.db.get(AiTcSuite, s.suite_id)
            if suite:
                suite_name = suite.name
        return project_name, suite_name

    # ═══════════════ 规范解析（AI 任务执行统一入口） ═══════════════

    async def resolve_specs_text(
        self,
        task_type: str,
        project_id: int | None = None,
        suite_id: int | None = None,
    ) -> tuple[list[int], str]:
        """按场景自动解析适用规范，返回 (规范ID列表, 拼接文本)。

        匹配规则:
        - general / common_issues: 项目级(project_id=当前项目)优先，否则全局(project_id IS NULL)
        - module_specific: 沿 suite_id 祖先链（含自身，近→远）回溯匹配，
          命中所有绑定在祖先层级的模块专用规范，按「近→远」排序
        - 仅 status=1 且 content 非空的参与
        - 按 general → module_specific → common_issues 顺序拼接
        """
        from app.aitc.constants import SpecType
        rows = (await self.db.execute(
            select(AiTcSpec).where(
                AiTcSpec.task_type == task_type,
                AiTcSpec.status == 1,
                AiTcSpec.is_deleted == 0,
                AiTcSpec.content != "",
            ).order_by(AiTcSpec.sort_order, AiTcSpec.id)
        )).scalars().all()

        # 祖先链（含自身，近→远），用于 module_specific 回溯匹配
        ancestor_ids: list[int] = []
        if suite_id:
            ancestor_ids = await self._get_ancestor_suite_ids(suite_id)

        def pick(spec_type: str) -> list[AiTcSpec]:
            candidates = [s for s in rows if s.spec_type == spec_type]
            if spec_type == "module_specific":
                matched = [s for s in candidates if suite_id and s.suite_id in ancestor_ids]
                # 近→远排序：离当前模块越近的祖先规范越靠后（更贴近用例）
                matched.sort(key=lambda s: ancestor_ids.index(s.suite_id) if s.suite_id in ancestor_ids else len(ancestor_ids))
                return matched
            project_level = [s for s in candidates if project_id and s.project_id == project_id]
            return project_level or [s for s in candidates if s.project_id is None]

        picked = [s for st in self.SPEC_TYPE_ORDER for s in pick(st)]
        ids = [s.id for s in picked]
        parts = [f"【{self.SPEC_TYPE_TITLES.get(s.spec_type, s.spec_type)}】\n{s.content}" for s in picked]
        return ids, "\n\n".join(parts)

    async def _get_ancestor_suite_ids(self, suite_id: int) -> list[int]:
        """返回 suite_id 自身及其所有祖先 id（近→远，含自己）。

        沿 parent_id 逐级向上回溯，不依赖 tree_path（tree_path 格式历史数据不可靠）。
        """
        ids: list[int] = [suite_id]
        current = suite_id
        visited: set[int] = set()
        while current and current not in visited:
            visited.add(current)
            row = await self.db.execute(
                select(AiTcSuite.parent_id).where(AiTcSuite.id == current)
            )
            parent_id = row.scalar_one_or_none()
            if parent_id is None or parent_id == 0:
                break
            ids.append(parent_id)
            current = parent_id
        return ids

    async def load_specs_text(self, spec_ids: list[int]) -> str:
        """根据 ID 加载规范内容并拼接为文本。"""
        if not spec_ids:
            return ""
        rows = await self.db.execute(
            select(AiTcSpec).where(
                AiTcSpec.id.in_(spec_ids),
                AiTcSpec.is_deleted == 0,
            )
        )
        spec_type_names = {"general": "通用规范", "module_specific": "模块专用规范", "common_issues": "常见问题规范"}
        parts = []
        for s in rows.scalars().all():
            stype = spec_type_names.get(s.spec_type, s.spec_type)
            parts.append(f"【{stype}】\n{s.content}")
        return "\n\n".join(parts)

    # ═══════════════ VO 组装 ═══════════════

    def _spec_to_vo(
        self, s: AiTcSpec, project_name: str | None = None, suite_name: str | None = None
    ) -> SpecVO:
        return SpecVO(
            id=s.id, project_id=s.project_id, project_name=project_name,
            suite_id=s.suite_id, suite_name=suite_name,
            task_type=s.task_type, spec_type=s.spec_type,
            content=s.content, sort_order=s.sort_order, status=s.status,
            create_time=str(s.create_time) if s.create_time else None,
            update_time=str(s.update_time) if s.update_time else None,
        )
