"""任务引擎 — 创建任务、重跑、查询、确认编排。

所有数据库操作委托给 TaskStore + 各页 Service（CaseService / SampleService 等），
结果回写委托给 AI agent tasks/ 下各任务处理器。
后台执行逻辑已迁移到 app/ai/agent/tasks/__init__.py 的 execute_task_bg。
"""

import json
from datetime import datetime

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BusinessException
from app.pagination import PageResult
from app.response import ResultCode
from app.ai.config import resolve_ai_config
from app.aitc.task.store import TaskStore
from app.aitc.case.service import CaseService
from app.aitc.spec.service import SpecService
from app.aitc.script.service import ScriptService
from app.aitc.constants import (
    ConfirmStatus, ItemStatus, ScriptSource, TaskStatus, TaskType,
)
from app.ai.agent.tasks import get_task_handler
from app.aitc.models import AiTcCase, AiTcProject
from app.aitc.task.models import AiTcTask, AiTcTaskItem

from app.aitc.task.schemas import (
    TaskCreate, TaskQuery, TaskVO, TaskItemVO, TaskConfirmReq,
    ReviewItemReq, ReviewRecordVO,
)
from app.aitc.case.schemas import CaseVO, CaseStep


class TaskEngine:
    """AI 任务执行引擎。

    创建任务后写入 QUEUED 状态，由全局 TaskScheduler 调度器
    按 FIFO 顺序拉起执行（而非直接 asyncio.create_task）。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    @property
    def _svc(self) -> TaskStore:
        """当前请求 session 对应的 task store 实例。"""
        return TaskStore(self.db)

    @property
    def _spec_svc(self) -> SpecService:
        return SpecService(self.db)

    @property
    def _case_svc(self) -> CaseService:
        return CaseService(self.db)

    @property
    def _script_svc(self) -> ScriptService:
        return ScriptService(self.db)

    # ═══════════════ 创建任务 ═══════════════

    async def create_task(self, form: TaskCreate, create_by: str = "") -> TaskVO:
        """创建 AI 任务，验证参数，写入 DB（QUEUED 状态），由调度器拉起执行。"""
        svc = self._svc

        # 验证项目
        if not await svc.verify_project_exists(form.project_id):
            raise BusinessException(code=ResultCode.DATA_NOT_FOUND, msg="项目不存在")

        # 确定用例范围
        if form.case_ids:
            case_ids = form.case_ids
        else:
            case_ids = await svc.get_subtree_case_ids(form.suite_id)

        if not case_ids:
            raise BusinessException(code=ResultCode.DATA_NOT_FOUND, msg="套件下无用例")

        # 加载 AI 配置
        ai_config = resolve_ai_config(form.task_type)

        # 解析规范 ID（已记录到任务，调度器执行时再按 ID 加载全文）
        spec_ids, _ = await self._spec_svc.resolve_specs_text(
            form.task_type, form.project_id, form.suite_id
        )
        if form.spec_ids:
            spec_ids = form.spec_ids

        # 加载用例摘要并创建任务记录 + 明细
        case_briefs = await svc.get_case_briefs(case_ids)
        task = await svc.create_task_record(
            task_type=form.task_type,
            project_id=form.project_id,
            suite_id=form.suite_id,
            spec_ids=spec_ids if spec_ids else None,
            ai_config_id=ai_config.id if ai_config else None,
            model=ai_config.model if ai_config else None,
            total_count=len(case_ids),
            create_by=create_by,
            session_id=form.session_id,
        )
        await svc.create_task_items(task.id, case_briefs)

        # 提交事务，确保后台任务能读取到刚创建的数据
        await self.db.commit()

        logger.info(
            f"Task created: id={task.id} type={form.task_type} "
            f"cases={len(case_briefs)} ai_config={ai_config.model if ai_config else 'default'}"
        )

        # 任务已写入 QUEUED 状态，由全局调度器 TaskScheduler 按 FIFO 拉起执行
        return self._task_to_vo(task)

    # ═══════════════ 重新执行 ═══════════════

    async def rerun_task(self, task_id: int) -> None:
        """重置任务状态和明细结果，放入队列等待调度器拉起。"""
        svc = self._svc

        task = await svc.get_task(task_id)
        if task is None:
            raise BusinessException(code=ResultCode.DATA_NOT_FOUND, msg="任务不存在")

        if task.status == TaskStatus.RUNNING:
            raise BusinessException(code=ResultCode.PARAM_VALID_FAIL, msg="任务正在运行中，无法重跑")

        # 重置任务状态
        task.status = TaskStatus.QUEUED
        task.done_count = 0
        task.error_msg = None
        task.input_tokens = 0
        task.output_tokens = 0
        task.update_time = datetime.now()

        # 重置所有明细：清空结果，回到待处理
        await svc.reset_task_items(task_id)
        await self.db.flush()

        # 更新 AI 配置快照（rerun 后可能换了配置）
        ai_config = resolve_ai_config(task.task_type)
        if ai_config:
            task.ai_config_id = ai_config.id
            task.model = ai_config.model
        else:
            task.ai_config_id = None
            task.model = None

        # 更新规范记录（按场景自动解析）
        spec_ids, _ = await self._spec_svc.resolve_specs_text(
            task.task_type, task.project_id, task.suite_id
        )
        if spec_ids:
            task.spec_ids = spec_ids

        await self.db.commit()
        logger.info(f"Task {task_id} rerun triggered, queued for scheduler")

    # ═══════════════ 任务查询 ═══════════════

    async def get_task_page(self, query: TaskQuery) -> PageResult:
        return await self._svc.get_task_page(query)

    async def get_task_detail(self, task_id: int) -> dict:
        """获取任务详情 + 明细列表。"""
        svc = self._svc

        task = await svc.get_task(task_id)
        if task is None:
            raise BusinessException(code=ResultCode.DATA_NOT_FOUND, msg="任务不存在")

        # 项目名
        proj = await self.db.get(AiTcProject, task.project_id)
        pname = proj.name if proj else ""

        # 套件全路径
        sname = await svc.get_suite_full_path(task.suite_id)

        task_vo = self._task_to_vo(task, pname, sname)

        # 明细列表
        items = await svc.get_task_items(task_id)
        item_vos = [self._task_item_to_vo(it) for it in items]

        return {"task": task_vo, "items": item_vos}

    async def get_task_items(self, task_id: int) -> list[TaskItemVO]:
        items = await self._svc.get_task_items(task_id)
        return [self._task_item_to_vo(it) for it in items]

    # ═══════════════ 确认任务结果 ═══════════════

    async def confirm_task_items(
        self, task_id: int, form: TaskConfirmReq, reviewed_by: str = "", reviewer_ip: str = ""
    ) -> None:
        """确认 AI 任务结果：
        - 采纳(1) / 编辑采纳(3)：将结果写入用例
        - 忽略(2)：仅标记状态
        """
        svc = self._svc

        task = await svc.get_task(task_id)
        if task is None:
            raise BusinessException(code=ResultCode.DATA_NOT_FOUND, msg="任务不存在")

        now = datetime.now()
        action_map = {
            ConfirmStatus.ACCEPTED: "accept",
            ConfirmStatus.IGNORED: "ignore",
            ConfirmStatus.EDITED_ACCEPTED: "edit_accept",
        }

        for ci in form.items:
            item = await svc.get_task_item(ci.item_id)
            if item is None or item.task_id != task_id:
                continue

            item.confirm_status = ci.confirm_status
            item.reviewed_by = reviewed_by
            item.review_time = now

            if ci.confirm_status == ConfirmStatus.EDITED_ACCEPTED and ci.final_content:
                item.final_content = ci.final_content

            # case_review：记录变更前快照
            if task.task_type == TaskType.CASE_REVIEW and ci.confirm_status in (
                ConfirmStatus.ACCEPTED, ConfirmStatus.EDITED_ACCEPTED
            ):
                before_snapshot = await svc.get_case_snapshot(item.case_id)

            # 根据任务类型写入目标
            if ci.confirm_status in (ConfirmStatus.ACCEPTED, ConfirmStatus.EDITED_ACCEPTED):
                await self._apply_result(svc, task.task_type, item, ci)

            # case_review：写审核记录（变更前后快照对比）
            if task.task_type == TaskType.CASE_REVIEW and ci.confirm_status in (
                ConfirmStatus.ACCEPTED, ConfirmStatus.EDITED_ACCEPTED
            ):
                after_snapshot = await svc.get_case_snapshot(item.case_id)
                await svc.create_review_record(
                    task_id=task_id,
                    task_item_id=ci.item_id,
                    case_id=item.case_id,
                    review_action=action_map.get(ci.confirm_status, "unknown"),
                    before_value=json.dumps(before_snapshot, ensure_ascii=False) if before_snapshot else None,
                    after_value=json.dumps(after_snapshot, ensure_ascii=False) if after_snapshot else None,
                    reviewer=reviewed_by,
                    reviewer_ip=reviewer_ip,
                    review_time=now,
                )
            # core_select / script_gen 不需要审核记录

        # 更新任务状态为已确认
        await svc.mark_task_confirmed(task_id)
        await self.db.flush()
        logger.info(f"Task {task_id} confirmed by {reviewed_by}")

    async def _apply_result(self, svc: TaskStore, task_type: str, item: AiTcTaskItem, ci):
        """将 AI 结果写入实际数据表，委托给对应任务处理器。"""
        handler = get_task_handler(task_type)
        output = item.output or {}
        await handler.apply_result(
            svc=svc,
            item=item,
            output=output,
            confirm_status=ci.confirm_status,
            final_content=ci.final_content if hasattr(ci, "final_content") else "",
            is_core=getattr(ci, "is_core", None),
        )

    # ═══════════════ 停止任务 ═══════════════

    async def stop_task(self, task_id: int) -> None:
        """停止一个正在排队或运行中的任务。"""
        svc = self._svc

        task = await svc.get_task(task_id)
        if task is None:
            raise BusinessException(code=ResultCode.DATA_NOT_FOUND, msg="任务不存在")

        if task.status not in (TaskStatus.QUEUED, TaskStatus.RUNNING):
            raise BusinessException(
                code=ResultCode.PARAM_VALID_FAIL,
                msg="只能停止排队中或运行中的任务",
            )

        # 写入 STOPPED 状态
        await svc.stop_task(task_id)
        await self.db.commit()

        # 通知调度器取消对应的后台协程（仅 RUNNING 状态）
        from app.ai.agent.tasks.scheduler import get_scheduler
        get_scheduler().cancel_execution(task_id)
        # 也尝试通知独立的 worker 取消（适配队列/worker 模型）
        try:
            from app.ai.agent.tasks.worker import get_worker

            get_worker().cancel_execution(task_id)
        except Exception:
            pass

        logger.info(f"Task {task_id} stopped, status={task.status}")

    # ═══════════════ 审核记录 & 单条审核 ═══════════════

    async def get_item_with_case(self, task_id: int, item_id: int) -> dict:
        """获取单条任务明细 + 关联用例详情（供审核页面使用）。"""
        svc = self._svc

        item = await svc.get_task_item(item_id)
        if item is None or item.task_id != task_id:
            raise BusinessException(code=ResultCode.DATA_NOT_FOUND, msg="明细不存在")

        case = await self.db.get(AiTcCase, item.case_id)
        case_vo: CaseVO | None = None
        if case:
            case_vo = CaseVO(
                id=case.id, project_id=case.project_id,
                project_prefix=case.project.prefix if case.project else "",
                suite_id=case.suite_id,
                suite_name=case.suite.name if case.suite else "",
                external_id=case.external_id, name=case.name, purpose=case.purpose,
                summary=case.summary, preconditions=case.preconditions, topo=case.topo,
                test_data=case.test_data,
                steps=[CaseStep(**s) for s in (case.steps or [])] if case.steps else [],
                importance=case.importance, is_core=case.is_core,
                core_reason=case.core_reason, core_source=case.core_source,
                is_sample=case.is_sample, review_status=case.review_status,
                script_count=case.script_count,
                create_time=str(case.create_time) if case.create_time else None,
                update_time=str(case.update_time) if case.update_time else None,
            )

        item_vo = self._task_item_to_vo(item)
        return {"item": item_vo, "case": case_vo}

    async def review_single_item(
        self, task_id: int, item_id: int, form: ReviewItemReq,
        reviewed_by: str = "", reviewer_ip: str = ""
    ) -> None:
        """逐字段审核单条任务明细，记录每个字段的审核操作到审计表。"""
        svc = self._svc

        item = await svc.get_task_item(item_id)
        if item is None or item.task_id != task_id:
            raise BusinessException(code=ResultCode.DATA_NOT_FOUND, msg="明细不存在")

        now = datetime.now()
        output: dict = item.output or {}
        case = await self.db.get(AiTcCase, item.case_id)

        # 逐字段审核记录
        for f in form.fields:
            if f.action == "accept":
                # 将 AI 建议的字段值写入用例
                actual_value = self._get_field_from_output(output, f.field_name)
                before_val = self._get_case_field_value(case, f.field_name) if case else ""
                if actual_value is not None:
                    await svc.update_case_field(item.case_id, f.field_name, actual_value)

                await svc.create_review_record(
                    task_id=task_id, task_item_id=item_id, case_id=item.case_id,
                    review_action="field_accept", field_name=f.field_name,
                    before_value=json.dumps(before_val, ensure_ascii=False),
                    after_value=json.dumps(actual_value, ensure_ascii=False),
                    reviewer=reviewed_by, reviewer_ip=reviewer_ip, review_time=now,
                )

            elif f.action == "edit_accept" and f.edited_value is not None:
                before_val = self._get_case_field_value(case, f.field_name) if case else ""
                await svc.update_case_field(item.case_id, f.field_name, f.edited_value)

                await svc.create_review_record(
                    task_id=task_id, task_item_id=item_id, case_id=item.case_id,
                    review_action="field_accept", field_name=f.field_name,
                    before_value=json.dumps(before_val, ensure_ascii=False),
                    after_value=json.dumps(f.edited_value, ensure_ascii=False),
                    reviewer=reviewed_by, reviewer_ip=reviewer_ip, review_time=now,
                    memo="manual_edit",
                )

            elif f.action == "ignore":
                before_val_snapshot = (
                    self._get_case_field_value(case, f.field_name) if case else ""
                )
                await svc.create_review_record(
                    task_id=task_id, task_item_id=item_id, case_id=item.case_id,
                    review_action="ignore", field_name=f.field_name,
                    before_value=json.dumps(before_val_snapshot, ensure_ascii=False),
                    after_value=None,
                    reviewer=reviewed_by, reviewer_ip=reviewer_ip, review_time=now,
                )

        # 更新整个 item 的确认状态
        if form.confirm_status == ConfirmStatus.ACCEPTED and not form.fields:
            # 无字段级别审核，整体采纳
            if output.get("script"):
                await self._apply_script_from_output(svc, item, output)

            snapshot = await svc.get_case_snapshot(item.case_id)
            await svc.create_review_record(
                task_id=task_id, task_item_id=item_id, case_id=item.case_id,
                review_action="accept",
                before_value=json.dumps(snapshot, ensure_ascii=False),
                after_value=None,
                reviewer=reviewed_by, reviewer_ip=reviewer_ip, review_time=now,
            )

        if form.confirm_status == ConfirmStatus.EDITED_ACCEPTED and form.final_content:
            item.final_content = form.final_content
            if output.get("script"):
                await self._apply_script_from_output(svc, item, output, form.final_content)

        all_accepted = form.fields and all(
            f.action in ("accept", "edit_accept") for f in form.fields
        )
        item.confirm_status = form.confirm_status or (
            ConfirmStatus.ACCEPTED if all_accepted else ConfirmStatus.IGNORED
        )
        item.reviewed_by = reviewed_by
        item.review_time = now

        await self.db.flush()

        # 该任务所有明细均已审核 → 标记任务为已确认
        pending_count = await self.db.scalar(
            select(func.count()).select_from(AiTcTaskItem).where(
                AiTcTaskItem.task_id == task_id,
                AiTcTaskItem.confirm_status == ConfirmStatus.PENDING,
                AiTcTaskItem.item_status == ItemStatus.SUCCESS,
                AiTcTaskItem.is_deleted == 0,
            )
        )
        if pending_count == 0:
            await svc.mark_task_confirmed(task_id)
            await self.db.flush()
        
        logger.info(f"Item {item_id} reviewed by {reviewed_by}, fields: {len(form.fields)}")

    async def get_review_records(self, task_id: int) -> list[ReviewRecordVO]:
        return await self._svc.get_review_records(task_id)

    # ── 审核辅助方法（纯 Python，无 DB 操作）──

    @staticmethod
    def _get_case_field_value(case: AiTcCase | None, field_name: str):
        """获取用例字段的原始值（覆盖全部可审核字段）。"""
        if case is None:
            return ""
        field_map = {
            "name": case.name,
            "purpose": case.purpose,
            "summary": case.summary,
            "importance": case.importance,
            "preconditions": case.preconditions,
            "test_data": case.test_data,
            "topo": case.topo,
            "steps": case.steps,
            "is_core": case.is_core,
            "core_reason": case.core_reason,
        }
        return field_map.get(field_name, "")

    @staticmethod
    def _get_field_from_output(output: dict, field_name: str):
        """从 AI 输出中提取字段的 suggested_value。

        兼容新旧两种格式：
        1. 新格式 fields[]: 从 fields 数组中按 field_name 查找 suggested_value
        2. 旧格式 rewritten: 从 rewritten dict 中取值
        """
        # 新格式优先：fields[]
        fields = output.get("fields") or []
        if fields:
            for f in fields:
                if isinstance(f, dict) and f.get("field_name") == field_name:
                    sv = f.get("suggested_value")
                    if sv is not None:
                        return sv
                    # 字段存在但无 suggested_value，返回 None（不 fallback）
                    return None

        # 旧格式：rewritten
        rewritten = output.get("rewritten") or output
        if isinstance(rewritten, dict):
            return rewritten.get(field_name)
        return None

    async def _apply_script_from_output(
        self, svc: TaskStore, item: AiTcTaskItem, output: dict,
        edited_content: str = "",
    ) -> None:
        """将脚本写入脚本库。"""
        script_content = edited_content or output.get("script", "")
        if not script_content:
            return
        await self._script_svc.create_script_record(
            case_id=item.case_id,
            language=output.get("language", "python"),
            framework=output.get("framework", "pytest"),
            content=script_content,
            source=ScriptSource.AI,
            task_item_id=item.id,
        )
        await self._case_svc.increment_case_script_count(item.case_id)

    # ═══════════════ 辅助方法 ═══════════════

    # （_load_prompt_from_file 已提取为模块级函数）

    # ═══════════════ VO 组装 ═══════════════

    @staticmethod
    def _task_to_vo(t: AiTcTask, project_name: str = "", suite_name: str = "") -> TaskVO:
        return TaskVO(
            id=t.id, task_type=t.task_type,
            project_id=t.project_id, project_name=project_name,
            suite_id=t.suite_id, suite_name=suite_name,
            prompt_id=None, spec_ids=t.spec_ids,
            ai_config_id=t.ai_config_id, model=t.model,
            status=t.status, total_count=t.total_count, done_count=t.done_count,
            session_id=t.session_id,
            input_tokens=t.input_tokens, output_tokens=t.output_tokens,
            error_msg=t.error_msg, create_by=t.create_by,
            create_time=str(t.create_time) if t.create_time else None,
        )

    @staticmethod
    def _task_item_to_vo(it: AiTcTaskItem) -> TaskItemVO:
        external_id = None
        project_prefix = ""
        purpose = ""
        importance = 2
        is_core = None
        try:
            if it.case:
                external_id = it.case.external_id
                purpose = it.case.purpose or ""
                importance = it.case.importance or 2
                is_core = it.case.is_core if it.case.is_core is not None else None
                if it.case.project:
                    project_prefix = it.case.project.prefix or ""
        except Exception:
            pass
        return TaskItemVO(
            id=it.id, task_id=it.task_id,
            case_id=it.case_id, case_name=it.case_name,
            project_prefix=project_prefix, external_id=external_id,
            purpose=purpose, importance=importance,
            output=it.output, item_status=it.item_status,
            confirm_status=it.confirm_status,
            final_content=it.final_content,
            reviewed_by=it.reviewed_by,
            review_time=it.review_time,
            is_core=is_core,
        )


