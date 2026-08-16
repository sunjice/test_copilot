"""AI 任务注册表 + 后台执行入口。

新增任务类型时，只需：
1. 在对应领域目录下添加任务文件
2. 在此处 import 并注册到 TASK_HANDLERS
"""

import asyncio

from app.aitc.constants import TaskStatus, TaskType
from app.ai.client import AiClient
from app.ai.config import resolve_ai_config
from app.aitc.task.store import TaskStore
from app.aitc.spec.service import SpecService
from app.ai.agent.tasks.base import BaseTask, TaskContext
from app.ai.agent.tasks.case.core_select import CoreSelectTask
from app.ai.agent.tasks.case.case_review import CaseReviewTask
from app.ai.agent.tasks.case.script_gen import ScriptGenTask
from app.ai.agent.tasks.case.case_complete import CaseCompleteTask


# ═══════════════ 任务注册表 ═══════════════

TASK_HANDLERS: dict[str, BaseTask] = {
    TaskType.CORE_SELECT: CoreSelectTask(),
    TaskType.CASE_REVIEW: CaseReviewTask(),
    TaskType.SCRIPT_GEN: ScriptGenTask(),
    TaskType.CASE_COMPLETE: CaseCompleteTask(),
}


def get_task_handler(task_type: str) -> BaseTask:
    """根据任务类型获取对应的处理器实例。"""
    handler = TASK_HANDLERS.get(task_type)
    if handler is None:
        raise ValueError(f"Unknown task type: {task_type}")
    return handler


# ═══════════════ 后台执行入口 ═══════════════

async def execute_task_bg(task_id: int, task_type: str):
    """后台执行一个 AI 任务。

    由 TaskScheduler 在任务抢占（QUEUED → RUNNING）后调用。
    自行从 DB 加载全部上下文（prompt / spec / ai_config），
    使用独立 DB 会话完成整个执行周期。
    """
    from app.database import AsyncSessionLocal
    from loguru import logger

    handler = get_task_handler(task_type)

    async with AsyncSessionLocal() as db:
        svc = TaskStore(db)
        try:
            # 加载任务记录
            task = await svc.get_task(task_id)
            if task is None:
                logger.error(f"Task {task_id} not found in background execution")
                return

            # 加载 AI 配置
            ai_config = resolve_ai_config(task_type)

            # 加载提示词
            prompt_content = handler.load_prompt()

            # 加载规范
            specs_text = ""
            if task.spec_ids:
                specs_text = await SpecService(db).load_specs_text(task.spec_ids)

            # 确保状态为 RUNNING
            await svc.update_task_status(task_id, TaskStatus.RUNNING)
            await db.commit()

            # 加载 task_items
            items = await svc.get_task_items(task_id)
            if not items:
                await svc.finish_task(task_id, TaskStatus.FAILED, "任务明细为空")
                await db.commit()
                return

            # 初始化 AI 客户端
            client = AiClient(ai_config)
            # 设置日志上下文，每次 LLM 调用自动写入 ai_run_events
            client.set_log_context(
                action=task_type,
                module="task_engine",
                task_id=task_id,
                session_id=task.session_id,
                provider=ai_config.provider,
            )

            # 构建上下文
            ctx = TaskContext(
                db=db,
                svc=svc,
                client=client,
                task_id=task_id,
                items=items,
                prompt=prompt_content,
                samples="",
                specs=specs_text,
            )

            # 执行前检查是否已被停止
            await db.refresh(task)
            if task.status == TaskStatus.STOPPED:
                logger.info(f"Task {task_id} was stopped before execution started")
                return

            # 执行
            await handler.execute(ctx)

            # 执行后再次检查（可能在执行过程中被停止）
            await db.refresh(task)
            if task.status == TaskStatus.STOPPED:
                logger.info(f"Task {task_id} was stopped, skipping completion logic")
                return

            # 更新 token 统计
            await svc.update_task_tokens(task_id, client.input_tokens, client.output_tokens)
            await svc.finish_task(task_id, TaskStatus.COMPLETED)
            await db.commit()

        except asyncio.CancelledError:
            logger.info(f"Task {task_id} cancelled by user")
            try:
                await svc.finish_task(task_id, TaskStatus.STOPPED, "用户手动停止")
                await db.commit()
            except Exception:
                pass


            raise

        except Exception as e:
            logger.exception(f"Task {task_id} execution failed: {e}")
            try:
                # 检查是否已被手动停止
                await db.refresh(task)
                if task.status == TaskStatus.STOPPED:
                    return
                await svc.finish_task(task_id, TaskStatus.FAILED, str(e)[:500])
                await db.commit()
            except Exception:
                pass
