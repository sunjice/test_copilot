"""任务域 — 数据存储层（纯 DB CRUD，无编排逻辑）。"""

from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.pagination import PageResult
from app.aitc.task.models import AiTcTask, AiTcTaskItem, AiTcReviewRecord
from app.aitc.case.models import AiTcProject, AiTcSuite, AiTcCase
from app.aitc.constants import TaskStatus, ItemStatus, ConfirmStatus


class TaskStore:
    """任务数据存储层。只负责单表 CRUD，不含跨表编排逻辑。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ═══════════════ Task 基础查询 ═══════════════

    async def get_task(self, task_id: int) -> AiTcTask | None:
        result = await self.db.execute(
            select(AiTcTask).where(AiTcTask.id == task_id, AiTcTask.is_deleted == 0)
        )
        return result.scalar_one_or_none()

    async def get_task_items(self, task_id: int) -> list[AiTcTaskItem]:
        rows = await self.db.execute(
            select(AiTcTaskItem).where(
                AiTcTaskItem.task_id == task_id,
                AiTcTaskItem.is_deleted == 0,
            ).order_by(AiTcTaskItem.id)
        )
        return list(rows.scalars().all())

    async def get_task_item(self, item_id: int) -> AiTcTaskItem | None:
        return await self.db.get(AiTcTaskItem, item_id)

    async def get_task_page(self, query) -> PageResult:
        conditions = [AiTcTask.is_deleted == 0]
        if query.projectId is not None:
            conditions.append(AiTcTask.project_id == query.projectId)
        if query.taskType:
            conditions.append(AiTcTask.task_type == query.taskType)
        if query.status is not None:
            conditions.append(AiTcTask.status == query.status)
        stmt = select(AiTcTask).where(*conditions).order_by(AiTcTask.id.desc())
        count_q = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0
        offset = (query.pageNum - 1) * query.pageSize
        rows = await self.db.execute(stmt.offset(offset).limit(query.pageSize))
        items = rows.scalars().all()
        # 批量取项目名
        pids = list({t.project_id for t in items})
        pname_map: dict[int, str] = {}
        if pids:
            prows = await self.db.execute(
                select(AiTcProject.id, AiTcProject.name).where(AiTcProject.id.in_(pids))
            )
            pname_map = {r.id: r.name for r in prows}
        # 批量取套件全路径
        sids = list({t.suite_id for t in items})
        sname_map: dict[int, str] = {}
        if sids:
            for sid in sids:
                sname_map[sid] = await self._get_suite_full_path(sid)
        from app.aitc.task.schemas import TaskVO
        vos = []
        for t in items:
            vos.append(TaskVO(
                id=t.id, task_type=t.task_type,
                project_id=t.project_id, project_name=pname_map.get(t.project_id, ""),
                suite_id=t.suite_id, suite_name=sname_map.get(t.suite_id, ""),
                prompt_id=None,
                spec_ids=t.spec_ids,
                ai_config_id=t.ai_config_id, model=t.model,
                status=t.status, total_count=t.total_count, done_count=t.done_count,
                input_tokens=t.input_tokens, output_tokens=t.output_tokens,
                error_msg=t.error_msg, create_by=t.create_by,
                create_time=str(t.create_time) if t.create_time else None,
            ))
        return PageResult(records=vos, total=total, pageNum=query.pageNum, pageSize=query.pageSize)

    async def verify_project_exists(self, project_id: int) -> bool:
        row = await self.db.execute(
            select(AiTcProject).where(AiTcProject.id == project_id, AiTcProject.is_deleted == 0)
        )
        return row.scalar_one_or_none() is not None

    async def get_subtree_case_ids(self, suite_id: int) -> list[int]:
        """获取指定套件及其所有子套件的用例 ID 列表。

        纯 parent_id 递归（不依赖 tree_path，因 tree_path 格式历史数据不可靠）。
        """
        suite = await self.db.get(AiTcSuite, suite_id)
        if suite is None:
            return []
        # parent_id 递归收集子树套件
        all_suite_ids: list[int] = [suite_id]
        current: list[int] = [suite_id]
        while current:
            rows = await self.db.execute(
                select(AiTcSuite.id).where(
                    AiTcSuite.parent_id.in_(current),
                    AiTcSuite.is_deleted == 0,
                )
            )
            children = [r[0] for r in rows]
            if not children:
                break
            all_suite_ids.extend(children)
            current = children
        case_rows = await self.db.execute(
            select(AiTcCase.id).where(
                AiTcCase.suite_id.in_(all_suite_ids),
                AiTcCase.is_deleted == 0,
            )
        )
        return [r[0] for r in case_rows]

    async def get_suite_full_path(self, suite_id: int | None) -> str:
        """根据 tree_path 获取套件完整路径，如 根模块 / 子模块 / 当前。"""
        if suite_id is None:
            return ""
        return await self._get_suite_full_path(suite_id)

    async def get_case_briefs(self, case_ids: list[int]) -> list[dict]:
        rows = await self.db.execute(
            select(AiTcCase.id, AiTcCase.name).where(AiTcCase.id.in_(case_ids))
        )
        return [{"id": r.id, "name": r.name} for r in rows]

    async def get_case_snapshot(self, case_id: int) -> dict | None:
        case = await self.db.get(AiTcCase, case_id)
        if case is None:
            return None
        return {
            "name": case.name or "",
            "summary": case.summary or "",
            "preconditions": case.preconditions or "",
            "test_data": case.test_data or "",
            "steps": case.steps or [],
            "is_core": case.is_core,
            "core_reason": case.core_reason or "",
        }

    async def update_case_field(self, case_id: int, field_name: str, value) -> None:
        """更新用例的单个字段（仅修改内存对象，不单独 flush）。"""
        case = await self.db.get(AiTcCase, case_id)
        if case is None:
            return
        # SmallInteger 字段需要转为 int
        if field_name in ("importance", "is_core"):
            value = int(value)
        setattr(case, field_name, value)
        case.update_time = datetime.now()

    # ═══════════════ Task 写操作 ═══════════════

    async def create_task_record(
        self, task_type: str, project_id: int, suite_id: int,
        spec_ids: list[int] | None,
        ai_config_id: int | None, model: str | None,
        total_count: int, create_by: str,
        session_id: int | None = None,
    ) -> AiTcTask:
        task = AiTcTask(
            task_type=task_type,
            project_id=project_id,
            suite_id=suite_id,
            spec_ids=spec_ids or None,
            ai_config_id=ai_config_id,
            model=model,
            status=TaskStatus.QUEUED,
            total_count=total_count,
            done_count=0,
            create_by=create_by,
            session_id=session_id,
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def create_task_items(self, task_id: int, case_briefs: list[dict]) -> None:
        for c in case_briefs:
            item = AiTcTaskItem(
                task_id=task_id,
                case_id=c["id"],
                case_name=c["name"],
                item_status=ItemStatus.PENDING,
                confirm_status=ConfirmStatus.PENDING,
            )
            self.db.add(item)
        await self.db.flush()

    async def update_task_status(self, task_id: int, status: int) -> None:
        task = await self.db.get(AiTcTask, task_id)
        if task:
            task.status = status
            task.update_time = datetime.now()

    async def update_task_done_count(self, task_id: int, done_count: int) -> None:
        task = await self.db.get(AiTcTask, task_id)
        if task:
            task.done_count = done_count
            task.update_time = datetime.now()

    async def finish_task(self, task_id: int, status: int, error_msg: str = "") -> None:
        task = await self.db.get(AiTcTask, task_id)
        if task:
            task.status = status
            task.error_msg = error_msg or None
            task.update_time = datetime.now()

    async def update_task_tokens(self, task_id: int, input_tokens: int, output_tokens: int) -> None:
        task = await self.db.get(AiTcTask, task_id)
        if task:
            task.input_tokens = input_tokens
            task.output_tokens = output_tokens

    async def mark_task_confirmed(self, task_id: int) -> None:
        task = await self.db.get(AiTcTask, task_id)
        if task:
            task.status = TaskStatus.CONFIRMED
            task.update_time = datetime.now()

    async def stop_task(self, task_id: int) -> None:
        """将任务状态置为已停止。仅 QUEUED/RUNNING 状态可停止。"""
        task = await self.db.get(AiTcTask, task_id)
        if task:
            task.status = TaskStatus.STOPPED
            task.update_time = datetime.now()

    async def reset_task_items(self, task_id: int) -> None:
        await self.db.execute(
            text(
                "UPDATE ai_tc_task_items SET item_status = 0, confirm_status = 0, "
                "output = NULL, final_content = NULL, reviewed_by = NULL, review_time = NULL, "
                "update_time = NOW() "
                "WHERE task_id = :tid AND is_deleted = 0"
            ),
            {"tid": task_id},
        )

    # ═══════════════ 审核记录 ═══════════════

    async def create_review_record(self, **kwargs) -> AiTcReviewRecord:
        record = AiTcReviewRecord(**kwargs)
        self.db.add(record)
        return record

    async def get_review_records(self, task_id: int) -> list:
        from app.aitc.task.schemas import ReviewRecordVO
        rows = await self.db.execute(
            select(AiTcReviewRecord).where(
                AiTcReviewRecord.task_id == task_id,
            ).order_by(AiTcReviewRecord.id.desc())
        )
        records = rows.scalars().all()
        case_ids = [r.case_id for r in records if r.case_id]
        case_name_map = {}
        if case_ids:
            case_rows = await self.db.execute(
                select(AiTcCase.id, AiTcCase.name).where(AiTcCase.id.in_(case_ids))
            )
            case_name_map = {r[0]: r[1] for r in case_rows}
        return [
            ReviewRecordVO(
                id=r.id, task_id=r.task_id, task_item_id=r.task_item_id,
                case_id=r.case_id, case_name=case_name_map.get(r.case_id),
                review_action=r.review_action, field_name=r.field_name,
                before_value=r.before_value, after_value=r.after_value,
                reviewer=r.reviewer, reviewer_ip=r.reviewer_ip,
                review_time=r.review_time, memo=r.memo,
                create_time=r.create_time,
            )
            for r in records
        ]

    # ═══════════════ 内部辅助 ═══════════════

    async def _get_suite_full_path(self, suite_id: int) -> str:
        suite = await self.db.get(AiTcSuite, suite_id)
        if suite is None:
            return ""
        ancestor_ids: list[int] = []
        if suite.tree_path:
            for part in suite.tree_path.split(","):
                part = part.strip().lstrip("$")
                if part and part != "0":
                    ancestor_ids.append(int(part))
        ancestor_ids.append(suite_id)
        if not ancestor_ids:
            return suite.name
        rows = await self.db.execute(
            select(AiTcSuite.id, AiTcSuite.name).where(AiTcSuite.id.in_(ancestor_ids))
        )
        name_map: dict[int, str] = {r.id: r.name for r in rows}
        names = [name_map.get(aid, "") for aid in ancestor_ids]
        return " / ".join(filter(None, names))
