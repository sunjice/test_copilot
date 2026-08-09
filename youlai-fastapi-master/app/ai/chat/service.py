"""AI 对话系统 — Chat Service 层（会话/消息/草稿 CRUD）。"""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.exceptions import BusinessException
from app.ai.chat.models import ChatSession, ChatMessage, ChatDraft, AiUsageLog
from app.ai.chat.schemas import (
    SessionCreate, SessionUpdate, SessionVO,
    MessageVO, DraftVO, DraftConfirmReq,
    ContextSetReq,
)
from app.ai.config import AiConfigSnapshot


class ChatService:
    """Chat 对话系统业务逻辑。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ═══════════════ 会话 CRUD ═══════════════

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

    async def list_sessions(
        self, domain: str | None = None, user_id: int | None = None,
    ) -> list[SessionVO]:
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
        # 全量替换而非 merge，防止旧值（如已清空的 current_case_id）残留
        session.context_json = req.context_json or {}
        session.update_time = datetime.now()
        await self.db.flush()

    # ═══════════════ 消息 CRUD ═══════════════

    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        msg_type: str = "text",
        metadata: dict | None = None,
        draft_id: int | None = None,
    ) -> MessageVO:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            msg_type=msg_type,
            content=content,
            metadata_json=metadata,
            draft_id=draft_id,
        )
        self.db.add(msg)
        # 更新会话消息计数和更新时间
        await self.db.execute(
            text(
                "UPDATE chat_sessions SET message_count = message_count + 1, "
                "update_time = :now WHERE id = :sid"
            ),
            {"now": datetime.now(), "sid": session_id},
        )
        # 自动生成标题（首条用户消息的前 30 字）
        if role == "user":
            await self._auto_title(session_id, content)

        await self.db.flush()
        await self.db.refresh(msg)
        return self._msg_to_vo(msg)

    async def get_messages(self, session_id: int, user_id: int | None = None) -> list[MessageVO]:
        # 先校验会话所有权
        await self._get_session_or_404(session_id, user_id)
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id)
        )
        msgs = result.scalars().all()
        return [self._msg_to_vo(m) for m in msgs]

    async def get_message_history(self, session_id: int, limit: int = 40, user_id: int | None = None) -> list[dict]:
        """获取最近 N 轮对话历史（供 LLM 使用）。"""
        msgs = await self.get_messages(session_id, user_id=user_id)
        recent = msgs[-limit:] if len(msgs) > limit else msgs
        return [
            {"role": m.role, "content": m.content}
            for m in recent
        ]

    async def update_last_confirm_card_metadata(self, session_id: int, metadata: dict) -> None:
        """找到会话中最新一条 confirm_card 消息，合并写入 metadata_json。"""
        await self.update_last_card_metadata_by_type(session_id, "confirm_card", metadata)

    async def update_last_card_metadata_by_type(self, session_id: int, msg_type: str, metadata: dict) -> None:
        """找到会话中最新一条指定类型的消息，合并写入 metadata_json。"""
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

    async def update_message_metadata_by_draft_id(self, draft_id: int, metadata: dict) -> None:
        """通过 draft_id 找到关联消息，合并写入 metadata_json。"""
        result = await self.db.execute(
            select(ChatMessage).where(ChatMessage.draft_id == draft_id)
        )
        msg = result.scalars().first()
        if msg is None:
            return
        merged = dict(msg.metadata_json or {})
        merged.update(metadata)
        msg.metadata_json = merged
        flag_modified(msg, "metadata_json")  # JSONB 列需显式标记变更
        await self.db.flush()

    # ═══════════════ 草稿 CRUD ═══════════════

    async def create_draft(
        self,
        session_id: int,
        message_id: int,
        draft_type: str,
        title: str,
        content_json: dict,
    ) -> DraftVO:
        draft = ChatDraft(
            session_id=session_id,
            message_id=message_id,
            draft_type=draft_type,
            title=title or draft_type,
            content_json=content_json,
            status="pending",
        )
        self.db.add(draft)
        await self.db.flush()
        await self.db.refresh(draft)
        return self._draft_to_vo(draft)

    async def get_draft(self, draft_id: int, user_id: int | None = None) -> DraftVO:
        draft = await self.db.get(ChatDraft, draft_id)
        if draft is None:
            raise BusinessException(f"草稿不存在: {draft_id}")
        # 校验所属会话所有权
        if user_id is not None:
            await self._get_session_or_404(draft.session_id, user_id)
        return self._draft_to_vo(draft)

    async def confirm_draft(self, draft_id: int, req: DraftConfirmReq, user_id: int | None = None) -> DraftVO:
        draft = await self.db.get(ChatDraft, draft_id)
        if draft is None:
            raise BusinessException(f"草稿不存在: {draft_id}")
        # 校验所属会话所有权
        if user_id is not None:
            await self._get_session_or_404(draft.session_id, user_id)

        if req.action == "confirm":
            draft.status = "confirmed"
            if req.edited_content:
                draft.content_json = req.edited_content
        elif req.action == "discard":
            draft.status = "discarded"
        else:
            raise BusinessException(f"不支持的操作: {req.action}")

        draft.confirmed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await self.db.flush()
        await self.db.refresh(draft)
        return self._draft_to_vo(draft)

    # ═══════════════ 用量日志 ═══════════════

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

    # ═══════════════ 私有方法 ═══════════════

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

    async def _auto_title(self, session_id: int, content: str):
        """自动设置会话标题（取首条消息前 30 字）。"""
        result = await self.db.execute(
            select(ChatSession.message_count).where(ChatSession.id == session_id)
        )
        count = result.scalar()
        if count == 1:  # 首条消息
            title = content[:30] + ("..." if len(content) > 30 else "")
            await self.db.execute(
                text("UPDATE chat_sessions SET title = :t WHERE id = :sid"),
                {"t": title, "sid": session_id},
            )

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

    @staticmethod
    def _msg_to_vo(m: ChatMessage) -> MessageVO:
        return MessageVO(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            msg_type=m.msg_type,
            content=m.content,
            metadata_json=m.metadata_json,
            draft_id=m.draft_id,
            create_time=m.create_time.strftime("%Y-%m-%d %H:%M:%S") if m.create_time else None,
        )

    @staticmethod
    def _draft_to_vo(d: ChatDraft) -> DraftVO:
        return DraftVO(
            id=d.id,
            session_id=d.session_id,
            message_id=d.message_id,
            draft_type=d.draft_type,
            title=d.title,
            content_json=d.content_json,
            status=d.status,
            confirmed_by=d.confirmed_by,
            confirmed_at=d.confirmed_at,
            create_time=d.create_time.strftime("%Y-%m-%d %H:%M:%S") if d.create_time else None,
        )
