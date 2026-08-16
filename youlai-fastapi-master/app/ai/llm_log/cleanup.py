"""AI 运行事件定时清理 — 每天凌晨 3:00 删除过期事件，分批删除避免长锁。"""

import asyncio
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import delete, select

from app.config import settings
from app.database import AsyncSessionLocal
from app.redis import get_redis
from app.ai.llm_log.models import AiRunEvent

# ═══════════════════ 清理配置 ═══════════════════

BATCH_SIZE = 5000                # 每批删除条数，避免长锁
CLEANUP_HOUR = 3                 # 每天清理执行的小时（凌晨 3 点）
LOCK_KEY = "aitc:llm_log:cleanup_lock"
LOCK_TTL = 3600                  # 锁 1 小时，远超单次清理耗时


class LlmLogCleanup:
    """LLM 日志清理器 — 每天定时删除过期日志。"""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """启动清理后台协程。"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "LlmLogCleanup started | retention=%dd batch=%d",
            settings.LLM_LOG_RETENTION_DAYS, BATCH_SIZE,
        )

    async def stop(self):
        """停止清理器。"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("LlmLogCleanup stopped")

    async def _run_loop(self):
        """主循环：等到达凌晨 3 点 → 获取分布式锁 → 执行清理 → 等下一个凌晨 3 点。"""
        while self._running:
            now = datetime.now()
            next_run = now.replace(hour=CLEANUP_HOUR, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()

            logger.info(
                "LlmLogCleanup next run at %s (in %.1fh)",
                next_run.strftime("%Y-%m-%d %H:%M:%S"), wait_seconds / 3600,
            )

            # 分段 sleep，以便能响应 stop()
            while self._running and wait_seconds > 0:
                chunk = min(wait_seconds, 60)
                await asyncio.sleep(chunk)
                wait_seconds -= chunk

            if not self._running:
                break

            # 获取 Redis 分布式锁
            if not await self._acquire_lock():
                logger.debug("LlmLogCleanup lock not acquired, another worker running")
                continue

            try:
                await self._do_cleanup()
            except Exception:
                logger.exception("LlmLogCleanup error")
            finally:
                await self._release_lock()

    async def _acquire_lock(self) -> bool:
        try:
            redis = await get_redis()
            acquired = await redis.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL)
            return bool(acquired)
        except Exception:
            logger.warning("LlmLogCleanup Redis unavailable, running anyway")
            return True

    async def _release_lock(self):
        try:
            redis = await get_redis()
            await redis.delete(LOCK_KEY)
        except Exception:
            pass

    async def _do_cleanup(self):
        """分批删除过期日志。"""
        cutoff = datetime.now() - timedelta(days=settings.LLM_LOG_RETENTION_DAYS)
        total_deleted = 0

        async with AsyncSessionLocal() as db:
            while True:
                # 子查询选出即将删除的 ID（避免 DELETE ... LIMIT 在不同 DB 的兼容问题）
                subq = (
                    select(AiRunEvent.id)
                    .where(AiRunEvent.create_time < cutoff)
                    .order_by(AiRunEvent.id)
                    .limit(BATCH_SIZE)
                )

                result = await db.execute(
                    delete(AiRunEvent).where(AiRunEvent.id.in_(subq))
                )
                await db.commit()

                batch_deleted = result.rowcount
                total_deleted += batch_deleted

                if batch_deleted < BATCH_SIZE:
                    break

                # 批次间休息 0.1s，避免持续占锁
                await asyncio.sleep(0.1)

        if total_deleted > 0:
            logger.info(
                "LlmLogCleanup deleted %d rows older than %s",
                total_deleted, cutoff.strftime("%Y-%m-%d"),
            )
        else:
            logger.debug("LlmLogCleanup nothing to delete")


# ═══════════════════ 全局单例 ═══════════════════

_cleanup: LlmLogCleanup | None = None


def get_llm_log_cleanup() -> LlmLogCleanup:
    """获取全局清理器单例。"""
    global _cleanup
    if _cleanup is None:
        _cleanup = LlmLogCleanup()
    return _cleanup
