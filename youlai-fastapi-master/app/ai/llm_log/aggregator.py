"""AI 用量每日汇总器 — 每天凌晨 2:30 聚合昨天的 ai_run_events 到 ai_usage_daily。

先汇总（2:30）再清理（3:00），确保过期事件在被删除前已完成聚合。
费用按 provider+model 的单价表计算，单价单位：元 / 1M tokens。
"""

import asyncio
from datetime import date, datetime, timedelta

from loguru import logger
from sqlalchemy import delete, func, select

from app.database import AsyncSessionLocal
from app.redis import get_redis
from app.ai.llm_log.models import AiRunEvent, AiUsageDaily

# ═══════════════════ 汇总配置 ═══════════════════

AGGREGATE_HOUR = 2                 # 每天汇总执行的小时（凌晨 2:30）
AGGREGATE_MINUTE = 30
LOCK_KEY = "aitc:llm_usage:aggregate_lock"
LOCK_TTL = 3600                    # 锁 1 小时

# ═══════════════════ 单价表（元 / 1M tokens）═══════════════════
# 命中缓存、未命中缓存、输出 单价不同，缺失的模型回退到 provider 默认价。

PRICES: dict[str, dict[str, dict[str, float]]] = {
    "deepseek": {
        "deepseek-chat": {"input_cache_hit": 0.5, "input_cache_miss": 2.0, "output": 8.0},
        "deepseek-reasoner": {"input_cache_hit": 1.0, "input_cache_miss": 4.0, "output": 16.0},
        "__default__": {"input_cache_hit": 0.5, "input_cache_miss": 2.0, "output": 8.0},
    },
    "openai": {
        "__default__": {"input_cache_hit": 0.0, "input_cache_miss": 0.0, "output": 0.0},
    },
    "local": {
        "__default__": {"input_cache_hit": 0.0, "input_cache_miss": 0.0, "output": 0.0},
    },
    "unknown": {
        "__default__": {"input_cache_hit": 0.0, "input_cache_miss": 0.0, "output": 0.0},
    },
}


def _get_price(provider: str, model: str) -> dict[str, float]:
    """获取某 provider+model 的单价，回退到 provider 默认价，再回退到 0。"""
    p = PRICES.get(provider, {})
    return p.get(model) or p.get("__default__") or {
        "input_cache_hit": 0.0, "input_cache_miss": 0.0, "output": 0.0,
    }


class UsageAggregator:
    """AI 用量每日汇总器 — 每天定时聚合昨天的用量。"""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """启动汇总后台协程。"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("UsageAggregator started | hour=%02d:%02d", AGGREGATE_HOUR, AGGREGATE_MINUTE)

    async def stop(self):
        """停止汇总器。"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("UsageAggregator stopped")

    async def _run_loop(self):
        """主循环：等到达凌晨 2:30 → 获取分布式锁 → 聚合 → 等下一个凌晨 2:30。"""
        while self._running:
            now = datetime.now()
            next_run = now.replace(
                hour=AGGREGATE_HOUR, minute=AGGREGATE_MINUTE, second=0, microsecond=0
            )
            if next_run <= now:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()

            logger.info(
                "UsageAggregator next run at %s (in %.1fh)",
                next_run.strftime("%Y-%m-%d %H:%M:%S"), wait_seconds / 3600,
            )

            while self._running and wait_seconds > 0:
                chunk = min(wait_seconds, 60)
                await asyncio.sleep(chunk)
                wait_seconds -= chunk

            if not self._running:
                break

            if not await self._acquire_lock():
                logger.debug("UsageAggregator lock not acquired, another worker running")
                continue

            try:
                await self.aggregate_yesterday()
            except Exception:
                logger.exception("UsageAggregator error")
            finally:
                await self._release_lock()

    async def _acquire_lock(self) -> bool:
        try:
            redis = await get_redis()
            acquired = await redis.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL)
            return bool(acquired)
        except Exception:
            logger.warning("UsageAggregator Redis unavailable, running anyway")
            return True

    async def _release_lock(self):
        try:
            redis = await get_redis()
            await redis.delete(LOCK_KEY)
        except Exception:
            pass

    async def aggregate_yesterday(self, target_date: date | None = None) -> int:
        """聚合指定日期（默认昨天）的 ai_run_events 到 ai_usage_daily，返回写入行数。"""
        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        async with AsyncSessionLocal() as db:
            # 先删除该日期的旧汇总（幂等重跑）
            await db.execute(
                delete(AiUsageDaily).where(AiUsageDaily.stat_date == target_date)
            )

            # 按 provider + model + api_base 分组聚合 llm_call 事件
            result = await db.execute(
                select(
                    AiRunEvent.provider,
                    AiRunEvent.model,
                    AiRunEvent.api_base,
                    func.count(AiRunEvent.id).label("request_count"),
                    func.coalesce(func.sum(AiRunEvent.prompt_tokens), 0).label("prompt_tokens"),
                    func.coalesce(func.sum(AiRunEvent.prompt_cache_hit_tokens), 0).label("prompt_cache_hit_tokens"),
                    func.coalesce(func.sum(AiRunEvent.prompt_cache_miss_tokens), 0).label("prompt_cache_miss_tokens"),
                    func.coalesce(func.sum(AiRunEvent.prompt_cache_write_tokens), 0).label("prompt_cache_write_tokens"),
                    func.coalesce(func.sum(AiRunEvent.completion_tokens), 0).label("completion_tokens"),
                    func.coalesce(func.sum(AiRunEvent.reasoning_tokens), 0).label("reasoning_tokens"),
                )
                .where(
                    AiRunEvent.event_type == "llm_call",
                    AiRunEvent.create_time >= datetime(target_date.year, target_date.month, target_date.day),
                    AiRunEvent.create_time < datetime(target_date.year, target_date.month, target_date.day)
                    + timedelta(days=1),
                )
                .group_by(AiRunEvent.provider, AiRunEvent.model, AiRunEvent.api_base)
            )

            rows = result.all()
            if not rows:
                logger.info("UsageAggregator nothing to aggregate for %s", target_date)
                return 0

            for r in rows:
                provider = r.provider or "unknown"
                model = r.model or "unknown"
                price = _get_price(provider, model)
                # 缓存写入按未命中价计（写入的 token 属于首次未命中的输入）
                cache_miss_price = price["input_cache_miss"]
                cost = (
                    r.prompt_cache_hit_tokens * price["input_cache_hit"]
                    + (r.prompt_cache_miss_tokens + r.prompt_cache_write_tokens) * cache_miss_price
                    + r.completion_tokens * price["output"]
                ) / 1_000_000

                db.add(AiUsageDaily(
                    stat_date=target_date,
                    provider=provider,
                    model=model,
                    api_base=r.api_base or "",
                    request_count=r.request_count,
                    prompt_tokens=r.prompt_tokens,
                    prompt_cache_hit_tokens=r.prompt_cache_hit_tokens,
                    prompt_cache_miss_tokens=r.prompt_cache_miss_tokens,
                    prompt_cache_write_tokens=r.prompt_cache_write_tokens,
                    completion_tokens=r.completion_tokens,
                    reasoning_tokens=r.reasoning_tokens,
                    cost_cny=round(cost, 6),
                ))

            await db.commit()
            logger.info(
                "UsageAggregator aggregated %d rows for %s", len(rows), target_date
            )
            return len(rows)


# ═══════════════════ 全局单例 ═══════════════════

_aggregator: UsageAggregator | None = None


def get_usage_aggregator() -> UsageAggregator:
    """获取全局汇总器单例。"""
    global _aggregator
    if _aggregator is None:
        _aggregator = UsageAggregator()
    return _aggregator
