"""TestLink 增量监控定时任务（每日）。

复用自研「计算下次运行时间 + asyncio.sleep + Redis 分布式锁」模式
（参考 app/ai/llm_log/aggregator.py）。

由于接口收敛为 3 个（无 get_changed_cases），增量检测策略：
    遍历已关联 TestLink 的用例（sync_status != 0），用 get_case_detail 拉当前内容，
    对比 synced_hash（或 synced_version）判断远端是否有变更。

冲突处理（方案 §7.2）：
    - 远端有变更 + 本地无未反写变更（sync_status != 2）→ 拉取更新，sync_status=1
    - 远端有变更 + 本地有未反写变更（sync_status == 2）→ sync_status=4（冲突）
    - 回声抑制：变更 modifier 为本系统且 modification_ts 接近 last_push_at → 忽略
"""

import asyncio
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.redis import get_redis
from app.aitc.case.models import AiTcCase, AiTcProject
from app.aitc.testlink import get_client
from app.aitc.testlink.hashing import content_hash
from app.aitc.testlink.parser import parse_case_to_local

# 每日巡检时间（凌晨 1:00）
MONITOR_HOUR = 1
MONITOR_MINUTE = 0
LOCK_KEY = "aitc:testlink:monitor_lock"
LOCK_TTL = 3600


class TestLinkMonitor:
    """增量监控器 — 每天定时巡检远端变更。"""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("TestLinkMonitor started | %02d:%02d", MONITOR_HOUR, MONITOR_MINUTE)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("TestLinkMonitor stopped")

    async def _run_loop(self) -> None:
        while self._running:
            now = datetime.now()
            next_run = now.replace(hour=MONITOR_HOUR, minute=MONITOR_MINUTE, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()

            logger.info("TestLinkMonitor next run at %s", next_run.strftime("%Y-%m-%d %H:%M:%S"))
            while self._running and wait_seconds > 0:
                chunk = min(wait_seconds, 60)
                await asyncio.sleep(chunk)
                wait_seconds -= chunk

            if not self._running:
                break

            if not await self._acquire_lock():
                logger.debug("TestLinkMonitor lock not acquired")
                continue
            try:
                await self.run_once()
            except Exception:
                logger.exception("TestLinkMonitor error")
            finally:
                await self._release_lock()

    async def _acquire_lock(self) -> bool:
        try:
            redis = await get_redis()
            return bool(await redis.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL))
        except Exception:
            logger.warning("TestLinkMonitor Redis unavailable, running anyway")
            return True

    async def _release_lock(self) -> None:
        try:
            redis = await get_redis()
            await redis.delete(LOCK_KEY)
        except Exception:
            pass

    async def run_once(self) -> dict:
        """执行一次增量巡检，返回统计。"""
        stats = {"checked": 0, "updated": 0, "conflicts": 0, "skipped": 0}
        client = get_client()

        async with AsyncSessionLocal() as db:
            # 所有已关联 TestLink 的项目
            rows = await db.execute(
                select(AiTcProject.id).where(AiTcProject.testlink_project_id.isnot(None))
            )
            project_ids = [r[0] for r in rows]

            for pid in project_ids:
                case_rows = await db.execute(
                    select(AiTcCase).where(
                        AiTcCase.project_id == pid,
                        AiTcCase.sync_status != 0,
                        AiTcCase.is_deleted == 0,
                    )
                )
                cases = case_rows.scalars().all()

                # 收集 testlink_tc_id
                tl_ids: list[str] = []
                for c in cases:
                    tl_id = (c.testlink_tc_id and str(c.testlink_tc_id)) or c.external_id
                    if tl_id:
                        tl_ids.append(tl_id)

                if not tl_ids:
                    continue

                details = await client.get_case_detail(tl_ids)
                for c in cases:
                    stats["checked"] += 1
                    tl_id = (c.testlink_tc_id and str(c.testlink_tc_id)) or c.external_id
                    key = (tl_id or "").replace("-", "")
                    if key not in details:
                        # 远端已删除 → sync_status=6
                        c.sync_status = 6
                        continue

                    remote = parse_case_to_local(key, details[key].model_dump())
                    remote_hash = content_hash(remote)

                    # 回声抑制：本系统反写触发，忽略
                    if c.testlink_modifier == "system" and c.last_push_at:
                        delta = (datetime.now() - c.last_push_at).total_seconds()
                        if delta < 300:
                            stats["skipped"] += 1
                            continue

                    if remote_hash == c.synced_hash:
                        continue  # 无变更

                    # 远端有变更
                    if c.sync_status == 2:
                        # 本地有未反写变更 → 冲突
                        c.sync_status = 4
                        stats["conflicts"] += 1
                    else:
                        # 拉取更新
                        self._apply_remote(db, c, remote)
                        stats["updated"] += 1

            await db.commit()
        return stats

    def _apply_remote(self, db, case: AiTcCase, remote: dict) -> None:
        """用远端内容更新本地用例（无冲突时）。"""
        case.name = remote.get("name") or case.name
        case.purpose = remote.get("purpose")
        case.summary = remote.get("summary")
        case.preconditions = remote.get("preconditions")
        case.topo = remote.get("topo")
        case.test_data = remote.get("test_data")
        case.steps = remote.get("steps")
        case.summary_raw = remote.get("summary_raw")
        case.preconditions_raw = remote.get("preconditions_raw")
        case.steps_raw = remote.get("steps_raw")
        case.test_data_raw = remote.get("test_data_raw")
        case.steps_parse_status = remote.get("steps_parse_status", 0)
        case.sync_status = 1
        case.synced_hash = content_hash(remote)
        case.last_sync_at = datetime.now()


_monitor: TestLinkMonitor | None = None


def get_testlink_monitor() -> TestLinkMonitor:
    """获取全局监控单例。"""
    global _monitor
    if _monitor is None:
        _monitor = TestLinkMonitor()
    return _monitor
