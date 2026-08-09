"""TaskWorker：消费队列并执行任务。

提供启动/停止与取消执行接口，内部维护 active_executions。
"""
import asyncio
import json
from typing import Dict, Optional

from loguru import logger

from app.ai.agent.tasks.queue import dequeue_task
from app.ai.agent.tasks import execute_task_bg


class TaskWorker:
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._active_executions: Dict[int, asyncio.Task] = {}

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("TaskWorker started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        tasks = list(self._active_executions.values())
        if tasks:
            logger.info(f"Waiting for {len(tasks)} active worker executions to finish...")
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=120)

        logger.info("TaskWorker stopped")

    def cancel_execution(self, task_id: int):
        bg = self._active_executions.pop(task_id, None)
        if bg and not bg.done():
            bg.cancel()
            logger.info(f"Worker cancelled execution of task {task_id}")

    async def _run_loop(self):
        while self._running:
            try:
                item = await dequeue_task(block_timeout=5)
                if not item:
                    continue

                task_id = item.get("task_id")
                task_type = item.get("task_type")
                if not task_id or not task_type:
                    continue

                # 启动后台执行
                bg = asyncio.create_task(execute_task_bg(task_id, task_type))
                self._active_executions[task_id] = bg
                bg.add_done_callback(lambda t, tid=task_id: self._active_executions.pop(tid, None))
                logger.info(f"Worker launched task id={task_id} type={task_type}")

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Worker loop error")


_worker: Optional[TaskWorker] = None


def get_worker() -> TaskWorker:
    global _worker
    if _worker is None:
        _worker = TaskWorker()
    return _worker
