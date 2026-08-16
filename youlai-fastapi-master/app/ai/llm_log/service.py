"""AI 运行事件 — 查询/导出/用量统计服务。"""

from datetime import date

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.pagination import PageQuery, PageResult
from app.ai.llm_log.models import AiRunEvent, AiUsageDaily


class LlmLogService:
    """AI 运行事件查询与导出服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 分页查询 ──

    async def query_logs(
        self,
        page: PageQuery,
        *,
        session_id: int | None = None,
        message_id: int | None = None,
        action: str | None = None,
        status: str | None = None,
        module: str | None = None,
        provider: str | None = None,
    ) -> PageResult:
        """分页查询 AI 运行事件。"""
        conditions = []
        if session_id is not None:
            conditions.append(AiRunEvent.session_id == session_id)
        if message_id is not None:
            conditions.append(AiRunEvent.message_id == message_id)
        if action:
            conditions.append(AiRunEvent.action == action)
        if status:
            conditions.append(AiRunEvent.status == status)
        if module:
            conditions.append(AiRunEvent.module == module)
        if provider:
            conditions.append(AiRunEvent.provider == provider)

        stmt = select(AiRunEvent).where(*conditions).order_by(desc(AiRunEvent.create_time))
        count_q = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        offset = (page.pageNum - 1) * page.pageSize
        rows = await self.db.execute(stmt.offset(offset).limit(page.pageSize))
        records = [self._to_dict(row, compact=True) for row in rows.scalars().all()]

        return PageResult(records=records, total=total, pageNum=page.pageNum, pageSize=page.pageSize)

    # ── 一轮对话的完整轨迹（按 seq 平铺排序）──

    async def get_trace(self, message_id: int) -> list[dict]:
        """返回某一轮对话的完整调用轨迹，按 seq 升序。"""
        result = await self.db.execute(
            select(AiRunEvent)
            .where(AiRunEvent.message_id == message_id)
            .order_by(AiRunEvent.seq, AiRunEvent.id)
        )
        return [self._to_dict(row, compact=False) for row in result.scalars().all()]

    # ── 每轮用量汇总 ──

    async def get_message_usage(self, message_id: int) -> dict:
        """汇总某一轮对话的 token 用量（对齐前端轮结束用量面板）。"""
        result = await self.db.execute(
            select(
                func.count(AiRunEvent.id).label("request_count"),
                func.coalesce(func.sum(AiRunEvent.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(AiRunEvent.prompt_cache_hit_tokens), 0).label("prompt_cache_hit_tokens"),
                func.coalesce(func.sum(AiRunEvent.prompt_cache_miss_tokens), 0).label("prompt_cache_miss_tokens"),
                func.coalesce(func.sum(AiRunEvent.prompt_cache_write_tokens), 0).label("prompt_cache_write_tokens"),
                func.coalesce(func.sum(AiRunEvent.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(AiRunEvent.reasoning_tokens), 0).label("reasoning_tokens"),
            )
            .where(
                AiRunEvent.message_id == message_id,
                AiRunEvent.event_type == "llm_call",
            )
        )
        row = result.one()
        hit = int(row.prompt_cache_hit_tokens)
        miss = int(row.prompt_cache_miss_tokens)
        total_cache = hit + miss
        cache_hit_rate = round(hit / total_cache, 4) if total_cache > 0 else 0.0
        return {
            "request_count": int(row.request_count),
            "prompt_tokens": int(row.prompt_tokens),
            "prompt_cache_hit_tokens": hit,
            "prompt_cache_miss_tokens": miss,
            "prompt_cache_write_tokens": int(row.prompt_cache_write_tokens),
            "completion_tokens": int(row.completion_tokens),
            "reasoning_tokens": int(row.reasoning_tokens),
            "reply_tokens": int(row.completion_tokens) - int(row.reasoning_tokens),
            "cache_hit_rate": cache_hit_rate,
        }

    # ── 每日用量汇总（读 ai_usage_daily）──

    async def get_daily_usage(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> list[dict]:
        """查询按日汇总的用量，可按日期/供应商/模型过滤。"""
        conditions = []
        if start_date:
            conditions.append(AiUsageDaily.stat_date >= start_date)
        if end_date:
            conditions.append(AiUsageDaily.stat_date <= end_date)
        if provider:
            conditions.append(AiUsageDaily.provider == provider)
        if model:
            conditions.append(AiUsageDaily.model == model)

        stmt = select(AiUsageDaily).where(*conditions).order_by(
            desc(AiUsageDaily.stat_date), AiUsageDaily.provider, AiUsageDaily.model
        )
        rows = await self.db.execute(stmt)
        return [
            {
                "stat_date": r.stat_date.isoformat(),
                "provider": r.provider,
                "model": r.model,
                "api_base": r.api_base,
                "request_count": r.request_count,
                "prompt_tokens": r.prompt_tokens,
                "prompt_cache_hit_tokens": r.prompt_cache_hit_tokens,
                "prompt_cache_miss_tokens": r.prompt_cache_miss_tokens,
                "prompt_cache_write_tokens": r.prompt_cache_write_tokens,
                "completion_tokens": r.completion_tokens,
                "reasoning_tokens": r.reasoning_tokens,
                "cost_cny": float(r.cost_cny) if r.cost_cny is not None else 0.0,
            }
            for r in rows.scalars().all()
        ]

    # ── 导出（不分页，全部符合条件的数据）──

    async def export_logs(
        self,
        *,
        session_id: int | None = None,
        message_id: int | None = None,
        action: str | None = None,
        status: str | None = None,
        module: str | None = None,
        provider: str | None = None,
    ) -> list[dict]:
        """导出全部符合条件的 AI 运行事件。"""
        stmt = select(AiRunEvent)

        if session_id is not None:
            stmt = stmt.where(AiRunEvent.session_id == session_id)
        if message_id is not None:
            stmt = stmt.where(AiRunEvent.message_id == message_id)
        if action:
            stmt = stmt.where(AiRunEvent.action == action)
        if status:
            stmt = stmt.where(AiRunEvent.status == status)
        if module:
            stmt = stmt.where(AiRunEvent.module == module)
        if provider:
            stmt = stmt.where(AiRunEvent.provider == provider)

        stmt = stmt.order_by(desc(AiRunEvent.create_time))
        stmt = stmt.limit(5000)

        result = await self.db.execute(stmt)
        return [self._to_dict(row, compact=False) for row in result.scalars().all()]

    # ── 工具 ──

    @staticmethod
    def _to_dict(ev: AiRunEvent, compact: bool = True) -> dict:
        """ORM 对象 → 字典。compact=True 时不返回大字段。"""
        base = {
            "id": ev.id,
            "session_id": ev.session_id,
            "message_id": ev.message_id,
            "seq": ev.seq,
            "event_type": ev.event_type,
            "module": ev.module,
            "action": ev.action,
            "tool_call_id": ev.tool_call_id,
            "provider": ev.provider,
            "api_base": ev.api_base,
            "model": ev.model,
            "status": ev.status,
            "error_msg": ev.error_msg,
            "prompt_tokens": ev.prompt_tokens,
            "prompt_cache_hit_tokens": ev.prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": ev.prompt_cache_miss_tokens,
            "prompt_cache_write_tokens": ev.prompt_cache_write_tokens,
            "completion_tokens": ev.completion_tokens,
            "reasoning_tokens": ev.reasoning_tokens,
            "duration_ms": ev.duration_ms,
            "create_time": ev.create_time.isoformat() if ev.create_time else None,
        }
        if not compact:
            base["request_messages"] = ev.request_messages
            base["response_raw"] = ev.response_raw
            base["response_json"] = ev.response_json
        return base

    # ── 单条详情 ──

    async def get_log(self, log_id: int) -> dict | None:
        """获取单条事件详情，返回 dict。"""
        result = await self.db.execute(
            select(AiRunEvent).where(AiRunEvent.id == log_id)
        )
        ev = result.scalar_one_or_none()
        if ev is None:
            return None
        return self._to_dict(ev, compact=False)

    # ── 有事件的会话列表 ──

    async def get_log_sessions(self, limit: int = 50) -> list[dict]:
        """获取最近有 AI 调用的会话列表（给前端下拉框用）。"""
        rows = await self.db.execute(
            select(
                AiRunEvent.session_id,
                func.max(AiRunEvent.create_time).label("last_time"),
                func.count(AiRunEvent.id).label("log_count"),
            )
            .where(AiRunEvent.session_id.isnot(None))
            .group_by(AiRunEvent.session_id)
            .order_by(desc("last_time"))
            .limit(limit)
        )
        return [
            {
                "session_id": r.session_id,
                "last_time": r.last_time.isoformat() if r.last_time else None,
                "log_count": r.log_count,
            }
            for r in rows
        ]
