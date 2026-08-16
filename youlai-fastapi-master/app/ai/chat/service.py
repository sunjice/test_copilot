"""AI 对话系统 — Chat Service 层（会话/消息/用量日志）。"""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.exceptions import BusinessException
from app.ai.chat.models import ChatSession, ChatMessage, AiUsageLog
from app.ai.chat.schemas import (
    SessionCreate, SessionUpdate, SessionVO,
    MessageVO, ContextSetReq,
)


class SessionService:
    """会话管理服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, req: SessionCreate, user_id: int | None = None) -> SessionVO:
        session = ChatSession(
            title=req.title,
            domain=req.domain,
            context_json=req.context_json or {},
            message_count=0,
            is_pinned=0,
            user_id=user_id,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return self._session_to_vo(session)

    async def list_sessions(self, domain: str | None = None, user_id: int | None = None) -> list[SessionVO]:
        conditions = [ChatSession.is_deleted == 0]
        if domain:
            conditions.append(ChatSession.domain == domain)
        if user_id is not None:
            conditions.append(ChatSession.user_id == user_id)

        result = await self.db.execute(
            select(ChatSession)
            .where(*conditions)
            .order_by(ChatSession.is_pinned.desc(), ChatSession.update_time.desc())
        )
        sessions = result.scalars().all()
        return [self._session_to_vo(s) for s in sessions]

    async def get_session(self, session_id: int, user_id: int | None = None) -> SessionVO:
        session = await self._get_session_or_404(session_id, user_id)
        return self._session_to_vo(session)

    async def update_session(self, session_id: int, req: SessionUpdate, user_id: int | None = None) -> SessionVO:
        session = await self._get_session_or_404(session_id, user_id)
        if req.title is not None:
            session.title = req.title
        if req.is_pinned is not None:
            session.is_pinned = req.is_pinned
        session.update_time = datetime.now()
        await self.db.flush()
        await self.db.refresh(session)
        return self._session_to_vo(session)

    async def delete_session(self, session_id: int, user_id: int | None = None):
        session = await self._get_session_or_404(session_id, user_id)
        session.is_deleted = 1
        await self.db.flush()

    async def set_context(self, session_id: int, req: ContextSetReq, user_id: int | None = None):
        session = await self._get_session_or_404(session_id, user_id)
        if req.domain:
            session.domain = req.domain
        session.context_json = req.context_json or {}
        session.update_time = datetime.now()
        await self.db.flush()

    async def _get_session_or_404(self, session_id: int, user_id: int | None = None) -> ChatSession:
        conditions = [
            ChatSession.id == session_id,
            ChatSession.is_deleted == 0,
        ]
        if user_id is not None:
            conditions.append(ChatSession.user_id == user_id)
        result = await self.db.execute(
            select(ChatSession).where(*conditions)
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise BusinessException(f"会话不存在或无权访问: {session_id}")
        return session

    @staticmethod
    def _session_to_vo(s: ChatSession) -> SessionVO:
        return SessionVO(
            id=s.id,
            title=s.title,
            domain=s.domain,
            context_json=s.context_json,
            message_count=s.message_count,
            is_pinned=s.is_pinned,
            user_id=s.user_id,
            create_time=s.create_time.strftime("%Y-%m-%d %H:%M:%S") if s.create_time else None,
            update_time=s.update_time.strftime("%Y-%m-%d %H:%M:%S") if s.update_time else None,
        )


class MessageService:
    """消息管理服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.session = SessionService(db)

    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        msg_type: str = "text",
        metadata: dict | None = None,
    ) -> MessageVO:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            msg_type=msg_type,
            content=content,
            metadata_json=metadata,
        )
        self.db.add(msg)
        await self.db.execute(
            text(
                "UPDATE chat_sessions SET message_count = message_count + 1, "
                "update_time = :now WHERE id = :sid"
            ),
            {"now": datetime.now(), "sid": session_id},
        )
        if role == "user":
            await self._auto_title(session_id, content)
        await self.db.flush()
        await self.db.refresh(msg)
        return self._msg_to_vo(msg)

    async def get_messages(self, session_id: int, user_id: int | None = None) -> list[MessageVO]:
        await self.session._get_session_or_404(session_id, user_id)
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id)
        )
        msgs = result.scalars().all()
        return [self._msg_to_vo(m) for m in msgs]

    async def get_message_history(self, session_id: int, limit: int = 40, user_id: int | None = None) -> list[dict]:
        msgs = await self.get_messages(session_id, user_id=user_id)
        recent = msgs[-limit:] if len(msgs) > limit else msgs
        return [
            {"role": m.role, "content": m.content}
            for m in recent
        ]

    async def update_last_confirm_card_metadata(self, session_id: int, metadata: dict) -> None:
        await self.update_last_card_metadata_by_type(session_id, "confirm_card", metadata)

    async def update_last_card_metadata_by_type(self, session_id: int, msg_type: str, metadata: dict) -> None:
        result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.msg_type == msg_type,
            )
            .order_by(ChatMessage.id.desc())
            .limit(1)
        )
        msg = result.scalars().first()
        if msg is None:
            return
        merged = dict(msg.metadata_json or {})
        merged.update(metadata)
        msg.metadata_json = merged
        flag_modified(msg, "metadata_json")
        await self.db.flush()

    async def update_card_metadata_by_seq(
        self,
        session_id: int,
        msg_type: str,
        card_seq: int | None,
        metadata: dict,
    ) -> None:
        """按 card_seq 序号更新指定卡片的 metadata（多卡片并行时精确定位）。

        若 card_seq 为空（旧面板/旧数据兼容），回退到最后一张卡片。
        """
        if card_seq is None:
            return await self.update_last_card_metadata_by_type(session_id, msg_type, metadata)

        result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.msg_type == msg_type,
            )
            .order_by(ChatMessage.id.desc())
        )
        for msg in result.scalars().all():
            md = msg.metadata_json or {}
            if md.get("card_seq") == card_seq:
                merged = dict(md)
                merged.update(metadata)
                msg.metadata_json = merged
                flag_modified(msg, "metadata_json")
                await self.db.flush()
                return

    async def _auto_title(self, session_id: int, content: str):
        result = await self.db.execute(
            select(ChatSession.message_count).where(ChatSession.id == session_id)
        )
        count = result.scalar()
        if count == 1:
            title = content[:30] + ("..." if len(content) > 30 else "")
            await self.db.execute(
                text("UPDATE chat_sessions SET title = :t WHERE id = :sid"),
                {"t": title, "sid": session_id},
            )

    @staticmethod
    def _msg_to_vo(m: ChatMessage) -> MessageVO:
        return MessageVO(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            msg_type=m.msg_type,
            content=m.content,
            metadata_json=m.metadata_json,
            create_time=m.create_time.strftime("%Y-%m-%d %H:%M:%S") if m.create_time else None,
        )


class UsageLogService:
    """AI 用量日志服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_usage(
        self,
        module: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
        session_id: int | None = None,
        task_id: int | None = None,
    ):
        log = AiUsageLog(
            module=module,
            session_id=session_id,
            task_id=task_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            duration_ms=duration_ms,
        )
        self.db.add(log)
        await self.db.flush()


class ChatService:
    """旧 ChatService 封装，兼容现有调用。"""

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

    async def set_context(self, session_id: int, req: ContextSetReq, user_id: int | None = None):
        return await self.session.set_context(session_id, req, user_id=user_id)

    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        msg_type: str = "text",
        metadata: dict | None = None,
    ) -> MessageVO:
        return await self.message.add_message(session_id, role, content, msg_type=msg_type, metadata=metadata)

    async def get_messages(self, session_id: int, user_id: int | None = None) -> list[MessageVO]:
        return await self.message.get_messages(session_id, user_id=user_id)

    async def get_message_history(self, session_id: int, limit: int = 40, user_id: int | None = None) -> list[dict]:
        return await self.message.get_message_history(session_id, limit=limit, user_id=user_id)

    async def update_last_confirm_card_metadata(self, session_id: int, metadata: dict) -> None:
        return await self.message.update_last_confirm_card_metadata(session_id, metadata)

    async def update_last_card_metadata_by_type(self, session_id: int, msg_type: str, metadata: dict) -> None:
        return await self.message.update_last_card_metadata_by_type(session_id, msg_type, metadata)

    async def log_usage(
        self,
        module: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
        session_id: int | None = None,
        task_id: int | None = None,
    ):
        return await self.usage.log_usage(
            module=module,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=duration_ms,
            session_id=session_id,
            task_id=task_id,
        )
