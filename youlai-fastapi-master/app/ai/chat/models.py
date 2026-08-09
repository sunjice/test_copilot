"""AI 对话系统 — Chat 模块 ORM 模型（4 张表）。"""

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, BaseIdMixin, SoftDeleteMixin, TimestampMixin


class ChatSession(Base, BaseIdMixin, TimestampMixin, SoftDeleteMixin):
    """对话会话。"""
    __tablename__ = "chat_sessions"

    title: Mapped[str] = mapped_column(String(200), default="新对话", server_default="'新对话'", comment="会话标题")
    domain: Mapped[str] = mapped_column(
        String(50), default="case", server_default="'case'", comment="会话域 case/bug/analytics"
    )
    context_json: Mapped[dict | None] = mapped_column(JSONB, comment="页面上下文快照 {project_id, suite_id, ...}")
    message_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="消息数量")
    is_pinned: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0", comment="是否置顶 0-否 1-是")
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="所属用户ID（单用户模式可为空）"
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", lazy="selectin", order_by="ChatMessage.id"
    )

    __table_args__ = (
        Index("idx_chat_session_user", "user_id", "is_deleted"),
        Index("idx_chat_session_domain", "domain"),
    )


class ChatMessage(Base, BaseIdMixin, TimestampMixin):
    """对话消息（不需要软删除，消息不可变）。"""
    __tablename__ = "chat_messages"

    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chat_sessions.id"), nullable=False, comment="所属会话ID"
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="角色 user/assistant/system"
    )
    msg_type: Mapped[str] = mapped_column(
        String(30), default="text", server_default="'text'",
        comment="消息类型 text/action_card/task_card/confirm_card/clarify_card/help_card"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息正文（Markdown）")
    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="附加数据 {skill_name, tool_calls, tokens, execution_time_ms, ...}"
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages", lazy="selectin")

    __table_args__ = (
        Index("idx_chat_msg_session", "session_id", "id"),
    )


class AiUsageLog(Base, BaseIdMixin):
    """AI Token 用量统计。"""
    __tablename__ = "ai_usage_logs"

    module: Mapped[str] = mapped_column(
        String(50), default="chat", server_default="'chat'", comment="来源模块 chat/task_engine"
    )
    session_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="会话ID（chat 模块）"
    )
    task_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="任务ID（task_engine 模块）"
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False, comment="模型名称")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="输入 token")
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="输出 token")
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="总 token")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="耗时(毫秒)")
    created_at: Mapped[str] = mapped_column(
        String(32), default=func.now(), comment="创建时间"
    )

    __table_args__ = (
        Index("idx_usage_module", "module", "created_at"),
        Index("idx_usage_session", "session_id"),
    )
