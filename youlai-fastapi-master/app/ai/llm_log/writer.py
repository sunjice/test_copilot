"""LLM 运行事件写入器 — 使用独立 DB 会话写入 ai_run_events 表，不污染业务事务。"""

from loguru import logger as loguru_logger

from app.database import AsyncSessionLocal
from app.ai.llm_log.models import AiRunEvent


class LlmLogWriter:
    """AI 运行事件写入器 — 每次调用使用独立 DB 会话，异常不影响主流程。"""

    @staticmethod
    async def write(
        *,
        session_id: int | None = None,
        message_id: int | None = None,
        seq: int = 0,
        event_type: str = "llm_call",
        module: str = "chat",
        action: str = "",
        tool_call_id: str | None = None,
        provider: str = "",
        api_base: str = "",
        model: str = "",
        status: str = "success",
        error_msg: str | None = None,
        request_messages: list[dict] | None = None,
        response_raw: str | None = None,
        response_json: dict | list | None = None,
        prompt_tokens: int = 0,
        prompt_cache_hit_tokens: int = 0,
        prompt_cache_miss_tokens: int = 0,
        prompt_cache_write_tokens: int = 0,
        completion_tokens: int = 0,
        reasoning_tokens: int = 0,
        duration_ms: int = 0,
    ) -> int | None:
        """写入一条 AI 运行事件，返回记录 ID。异常时仅 log 不抛出。"""
        try:
            async with AsyncSessionLocal() as db:
                ev = AiRunEvent(
                    session_id=session_id,
                    message_id=message_id,
                    seq=seq,
                    event_type=event_type,
                    module=module,
                    action=action,
                    tool_call_id=tool_call_id,
                    provider=provider,
                    api_base=api_base,
                    model=model,
                    status=status,
                    error_msg=error_msg,
                    request_messages=request_messages,
                    response_raw=response_raw,
                    response_json=response_json,
                    prompt_tokens=prompt_tokens,
                    prompt_cache_hit_tokens=prompt_cache_hit_tokens,
                    prompt_cache_miss_tokens=prompt_cache_miss_tokens,
                    prompt_cache_write_tokens=prompt_cache_write_tokens,
                    completion_tokens=completion_tokens,
                    reasoning_tokens=reasoning_tokens,
                    duration_ms=duration_ms,
                )
                db.add(ev)
                await db.commit()
                await db.refresh(ev)
                return ev.id
        except Exception as e:
            loguru_logger.warning(f"Failed to write AI run event: {e}")
            return None
