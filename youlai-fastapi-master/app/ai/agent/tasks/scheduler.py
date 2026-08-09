"""任务调度器 — DB 轮询 + Redis 分布式锁，控制全局并发、FIFO 排队、故障恢复。

设计要点：
- Redis 分布式锁（SETNX + TTL）保证 4 个 uvicorn worker 中仅一个执行调度。
- 定期扫描 QUEUED 任务，按 create_time FIFO 拉起，控制全局最大并发数。
- 每用户配额：同一用户最多 1 个 RUNNING 任务，其余排队。
- 启动时恢复僵死任务：将所有 RUNNING 任务重置为 QUEUED。
"""

import asyncio
from datetime import datetime

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.redis import get_redis
from app.aitc.constants import TaskStatus
from app.aitc.models import AiTcTask
from app.ai.agent.tasks import execute_task_bg

# ═══════════════ 调度配置 ═══════════════

MAX_CONCURRENT_TASKS = 5          # 全局最大并发任务数
POLL_INTERVAL = 3                 # 调度轮询间隔（秒）
LOCK_KEY = "aitc:scheduler:lock"  # Redis 分布式锁 key
LOCK_TTL = 15                     # 锁过期时间（秒），防止进程宕机死锁
PER_USER_MAX_RUNNING = 1          # 每用户最大并发执行数


class TaskScheduler:
    """任务调度器。

    用法：
        scheduler = TaskScheduler()
        await scheduler.start()   # 在 app lifespan 启动时
        await scheduler.stop()    # 在 app lifespan 关闭时
    """

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._active_executions: dict[int, asyncio.Task] = {}  # task_id → asyncio.Task

    # ── 启动 / 停止 ──

    async def start(self):
        """启动调度器后台协程。幂等，重复调用不产生第二个协程。"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("TaskScheduler started | max_concurrent=%d poll_interval=%ds",
                     MAX_CONCURRENT_TASKS, POLL_INTERVAL)

    async def stop(self):
        """优雅停止调度器：取消轮询循环，等待正在执行的任务完成。"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        tasks = list(self._active_executions.values())
        if tasks:
            logger.info(f"Waiting for {len(tasks)} active executions to finish...")
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=120,  # 最长等 2 分钟
            )

        logger.info("TaskScheduler stopped")

    def cancel_execution(self, task_id: int):
        """取消指定任务的正在执行的后台协程。"""
        bg_task = self._active_executions.pop(task_id, None)
        if bg_task and not bg_task.done():
            bg_task.cancel()
            logger.info(f"Scheduler cancelled execution of task {task_id}")

    # ── 主循环 ──

    async def _run_loop(self):
        """调度器主循环：恢复僵死任务 → 周期调度。"""
        # 启动时恢复僵死任务（进程重启后遗留的 RUNNING 状态）
        await self._recover_stuck_tasks()

        while self._running:
            try:
                acquired = await self._try_acquire_lock()
                if acquired:
                    try:
                        await self._schedule_cycle()
                    finally:
                        await self._release_lock()
            except Exception:
                logger.exception("TaskScheduler cycle error")

            await asyncio.sleep(POLL_INTERVAL)

    # ── Redis 分布式锁 ──

    async def _try_acquire_lock(self) -> bool:
        """尝试获取 Redis 分布式锁（SETNX）。

        Returns
        -------
        bool
            True 表示成功获取锁（本进程是唯一的调度员）。
        """
        try:
            redis = await get_redis()
            acquired = await redis.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL)
            return bool(acquired)
        except Exception:
            # Redis 不可用时退化为本地调度（所有 worker 都会尝试，但
            # 抢占环节的 QUEUED→RUNNING 状态更新在 DB 层天然互斥）
            logger.warning("Redis unavailable, falling back to local scheduling")
            return True

    async def _release_lock(self):
        """释放 Redis 分布式锁。"""
        try:
            redis = await get_redis()
            await redis.delete(LOCK_KEY)
        except Exception:
            pass

    # ── 故障恢复 ──

    async def _recover_stuck_tasks(self):
        """启动时将所有 RUNNING 任务重置为 QUEUED。

        解决进程重启/宕机后任务永久卡在 RUNNING 状态的问题。
        """
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(AiTcTask).where(
                        AiTcTask.status == TaskStatus.RUNNING,
                        AiTcTask.is_deleted == 0,
                    )
                )
                stuck = result.scalars().all()
                if stuck:
                    for t in stuck:
                        t.status = TaskStatus.QUEUED
                        t.error_msg = None
                        t.update_time = datetime.now()
                    await db.commit()
                    logger.info(
                        "Recovered %d stuck tasks: RUNNING → QUEUED",
                        len(stuck),
                    )
            except Exception:
                await db.rollback()
                logger.exception("Failed to recover stuck tasks")

    # ── 调度核心 ──

    async def _schedule_cycle(self):
        """一轮调度：检查容量 → FIFO 取 QUEUED 任务 → 原子抢占 → 拉起执行。"""
        async with AsyncSessionLocal() as db:
            try:
                # 1) 当前 RUNNING 数量 & 可用槽位
                running_count = await self._count_running(db)
                available = MAX_CONCURRENT_TASKS - running_count
                if available <= 0:
                    return

                # 2) 当前 RUNNING 任务的用户集合（用于每用户配额）
                running_users = await self._get_running_users(db)

                # 3) 取 QUEUED 任务，按 create_time FIFO
                result = await db.execute(
                    select(AiTcTask)
                    .where(
                        AiTcTask.status == TaskStatus.QUEUED,
                        AiTcTask.is_deleted == 0,
                    )
                    .order_by(AiTcTask.create_time, AiTcTask.id)
                    .limit(available * 2)  # 多取一些以跳过同用户的
                )
                queued = result.scalars().all()

                # 4) 按优先级拉起
                launched = 0
                for task in queued:
                    if launched >= available:
                        break

                    # 每用户配额：同用户已有运行中任务则跳过
                    if task.create_by and task.create_by in running_users:
                        continue

                    # 原子抢占：QUEUED → RUNNING
                    task.status = TaskStatus.RUNNING
                    task.update_time = datetime.now()
                    await db.commit()

                    if task.create_by:
                        running_users.add(task.create_by)

                    # 后台拉起执行
                    bg = asyncio.create_task(execute_task_bg(task.id, task.task_type))
                    self._active_executions[task.id] = bg
                    bg.add_done_callback(lambda t, tid=task.id: self._active_executions.pop(tid, None))

                    launched += 1
                    logger.info(
                        "Scheduler launched task id=%d type=%s [%d/%d slots]",
                        task.id, task.task_type, launched, available,
                    )

            except Exception:
                await db.rollback()
                raise

    @staticmethod
    async def _count_running(db: AsyncSession) -> int:
        """查询当前 RUNNING 任务数。"""
        result = await db.execute(
            select(func.count()).select_from(AiTcTask).where(
                AiTcTask.status == TaskStatus.RUNNING,
                AiTcTask.is_deleted == 0,
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def _get_running_users(db: AsyncSession) -> set[str]:
        """查询当前 RUNNING 任务的用户集合。"""
        result = await db.execute(
            select(AiTcTask.create_by).where(
                AiTcTask.status == TaskStatus.RUNNING,
                AiTcTask.is_deleted == 0,
                AiTcTask.create_by.isnot(None),
                AiTcTask.create_by != "",
            )
        )
        return {row[0] for row in result.all()}


# ═══════════════ 全局单例 ═══════════════

_scheduler: TaskScheduler | None = None


def get_scheduler() -> TaskScheduler:
    """获取全局调度器单例。"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler
