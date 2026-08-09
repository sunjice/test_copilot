"""任务队列（基于 Redis 列表）。

队列项为 JSON 字符串：{"task_id": int, "task_type": str}
提供入队与阻塞出队接口。
"""
import json
from typing import Optional

from app.redis import get_redis

QUEUE_KEY = "aitc:task:queue"


async def enqueue_task(task_id: int, task_type: str) -> None:
    redis = await get_redis()
    payload = json.dumps({"task_id": task_id, "task_type": task_type})
    # 使用 RPUSH，消费者使用 BLPOP 从左侧弹出
    await redis.rpush(QUEUE_KEY, payload)


async def dequeue_task(block_timeout: int = 5) -> Optional[dict]:
    """阻塞出队：返回 dict 或 None（超时）。"""
    redis = await get_redis()
    # BLPOP 返回 (key, value) 或 None
    res = await redis.blpop(QUEUE_KEY, timeout=block_timeout)
    if not res:
        return None
    _, payload = res
    try:
        return json.loads(payload)
    except Exception:
        return None
"""任务队列包装器 — DB 队列查询与抢占逻辑。"""

from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.aitc.constants import TaskStatus
from app.aitc.models import AiTcTask


class TaskQueue:
    """数据库驱动的任务队列。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def recover_stuck_tasks(self) -> int:
        """将启动时残留的 RUNNING 任务重置为 QUEUED。"""
        result = await self.db.execute(
            select(AiTcTask).where(
                AiTcTask.status == TaskStatus.RUNNING,
                AiTcTask.is_deleted == 0,
            )
        )
        stuck = result.scalars().all()
        for task in stuck:
            task.status = TaskStatus.QUEUED
            task.error_msg = None
            task.update_time = datetime.now()
        if stuck:
            await self.db.commit()
        return len(stuck)

    async def count_running(self) -> int:
        """查询当前 RUNNING 任务数量。"""
        result = await self.db.execute(
            select(func.count()).select_from(AiTcTask).where(
                AiTcTask.status == TaskStatus.RUNNING,
                AiTcTask.is_deleted == 0,
            )
        )
        return result.scalar() or 0

    async def get_running_users(self) -> set[str]:
        """查询当前 RUNNING 任务对应的用户集合。"""
        result = await self.db.execute(
            select(AiTcTask.create_by).where(
                AiTcTask.status == TaskStatus.RUNNING,
                AiTcTask.is_deleted == 0,
                AiTcTask.create_by.isnot(None),
                AiTcTask.create_by != "",
            )
        )
        return {row[0] for row in result.all()}

    async def fetch_queued(self, limit: int) -> list[AiTcTask]:
        """按 FIFO 获取排队中的任务。"""
        result = await self.db.execute(
            select(AiTcTask)
            .where(
                AiTcTask.status == TaskStatus.QUEUED,
                AiTcTask.is_deleted == 0,
            )
            .order_by(AiTcTask.create_time, AiTcTask.id)
            .limit(limit)
        )
        return result.scalars().all()

    async def reserve_task(self, task: AiTcTask) -> None:
        """将一个 QUEUED 任务原子抢占为 RUNNING。"""
        task.status = TaskStatus.RUNNING
        task.update_time = datetime.now()
        await self.db.commit()
