import asyncio
import json
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chat.service import SessionService, MessageService, UsageLogService
from app.ai.chat.session_manager import SessionContext
from app.ai.chat.orchestrator import chat_orchestrator
from app.ai.config import resolve_ai_config
from app.ai.llm_log.writer import make_trace_id
from app.ai.chat.schemas import (
    SessionCreate, SessionUpdate, SessionVO,
    MessageSendReq, MessageVO,
    ContextSetReq,
)


class ChatUseCase:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.session = SessionService(db)
        self.message = MessageService(db)
        self.usage = UsageLogService(db)

    async def create_session(self, req: SessionCreate, user_id: int | None = None) -> SessionVO:
        return await self.session.create_session(req, user_id=user_id)

    async def list_sessions(self, domain: str | None = None, user_id: int | None = None) -> list[SessionVO]:
        return await self.session.list_sessions(domain=domain, user_id=user_id)

    async def get_session(self, session_id: int, user_id: int | None = None) -> SessionVO:
        return await self.session.get_session(session_id, user_id=user_id)

    async def update_session(self, session_id: int, req: SessionUpdate, user_id: int | None = None) -> SessionVO:
        return await self.session.update_session(session_id, req, user_id=user_id)

    async def delete_session(self, session_id: int, user_id: int | None = None):
        return await self.session.delete_session(session_id, user_id=user_id)

    async def get_messages(self, session_id: int, user_id: int | None = None) -> list[MessageVO]:
        return await self.message.get_messages(session_id, user_id=user_id)

    async def set_context(self, session_id: int, req: ContextSetReq, user_id: int | None = None):
        return await self.session.set_context(session_id, req, user_id=user_id)

    async def update_last_confirm_card_metadata(self, session_id: int, metadata: dict) -> None:
        return await self.message.update_last_confirm_card_metadata(session_id, metadata)

    async def update_last_card_metadata_by_type(self, session_id: int, msg_type: str, metadata: dict) -> None:
        return await self.message.update_last_card_metadata_by_type(session_id, msg_type, metadata)

    async def update_card_metadata_by_seq(
        self,
        session_id: int,
        msg_type: str,
        card_seq: int | None,
        metadata: dict,
    ) -> None:
        return await self.message.update_card_metadata_by_seq(session_id, msg_type, card_seq, metadata)

    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        msg_type: str = "text",
        metadata: dict | None = None,
    ) -> "MessageVO":
        return await self.message.add_message(session_id, role, content, msg_type=msg_type, metadata=metadata)

    async def send_message_stream(
        self,
        session_id: int,
        req: MessageSendReq,
        owner_id: int | None,
    ) -> AsyncGenerator[str, None]:
        # 0. 校验会话所有权
        session = await self.session.get_session(session_id, user_id=owner_id)

        # 1. 获取历史消息（必须在保存当前用户消息之前，避免 history 中包含当前消息）
        history = await self.message.get_message_history(session_id, limit=29, user_id=owner_id)

        # 2. 保存用户消息
        await self.message.add_message(session_id, "user", req.content)
        context = SessionContext(
            session_id=session_id,
            domain=session.domain,
            context_json=session.context_json or {},
        )

        # 3. 解析 AI 配置
        ai_config = resolve_ai_config("chat")

        # 4. 注入上下文
        context.working["db_session"] = self.db
        context.working["ai_config"] = ai_config
        trace_id = make_trace_id("chat", session_id)
        context.working["trace_id"] = trace_id

        # 单一事实来源：后端只产出一条 message 事件（parts 内嵌卡片），
        # 这里收集单条 message 并持久化一次。
        assistant_content: str = ""
        assistant_meta: dict = {}
        current_event = ""

        try:
            stream = chat_orchestrator.process_message(
                req.content, context, history
            )
            async for sse in stream:
                yield sse

                for line in sse.splitlines():
                    if line.startswith("event: "):
                        current_event = line[7:].strip()
                    elif line.startswith("data: "):
                        try:
                            data = json.loads(line[6:].strip())
                            if isinstance(data, dict) and current_event == "message":
                                assistant_content = data.get("content", "")
                                assistant_meta = data.get("metadata") or {}
                        except (json.JSONDecodeError, KeyError):
                            pass

            # 有内容或有 parts（卡片类消息 content 可能为空，但 parts 含卡片）都需持久化
            if assistant_content or assistant_meta.get("parts"):
                await self.message.add_message(
                    session_id, "assistant",
                    assistant_content,
                    msg_type="text",
                    metadata=assistant_meta,
                )

        except Exception as e:
            err_text = f"处理消息时出错: {str(e)}"
            await self.message.add_message(
                session_id, "assistant", err_text, msg_type="text",
                metadata={"error": str(e)},
            )
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

        last_meta = assistant_meta
        tokens = last_meta.get("tokens", {})
        if tokens:
            await self.usage.log_usage(
                module="chat",
                model=ai_config.model if ai_config else "unknown",
                prompt_tokens=tokens.get("prompt", 0),
                completion_tokens=tokens.get("completion", 0),
                duration_ms=last_meta.get("duration_ms", 0),
                session_id=session_id,
            )

        yield "event: done\ndata: {}\n\n"
