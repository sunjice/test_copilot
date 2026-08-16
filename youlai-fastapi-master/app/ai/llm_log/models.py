"""AI 运行轨迹与用量日志 — ORM 模型。

设计（对齐 DeepSeek Harness 的平铺 append-only 事件流，无树、无 parent_id）：
- ``ai_run_events``：一次 LLM / 工具调用 = 一行事件，按 session_id + message_id + seq
  平铺排序，即可还原一整轮对话的完整调用轨迹；token 用量字段与 DeepSeek 返回
  的 usage 字段名保持一致，供每轮/每日汇总统计。
- ``ai_usage_daily``：定时任务从 ``ai_run_events`` 聚合出的按日用量汇总表，
  用于看费用、看缓存命中率等。
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BaseIdMixin


class AiRunEvent(Base, BaseIdMixin):
    """AI 运行事件（平铺轨迹）— 每次 LLM 调用 / 工具调用记录一行。

    event_type 取值：
        turn_start / user_message / llm_call / tool_call / tool_result /
        assistant_message / turn_end
    其中 llm_call 事件才填充 token 用量与缓存字段。
    """
    __tablename__ = "ai_run_events"

    # ── 定位（会话 → 一轮 → 轮内顺序）──
    session_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="关联会话ID（一个对话界面）"
    )
    message_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="关联消息ID（一轮问答，用户一句 → AI 一回）"
    )
    seq: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="轮内单调递增序号"
    )

    # ── 事件类型 / 动作 ──
    event_type: Mapped[str] = mapped_column(
        String(40), default="llm_call", server_default="'llm_call'",
        comment="事件类型 turn_start/user_message/llm_call/tool_call/tool_result/assistant_message/turn_end",
    )
    module: Mapped[str] = mapped_column(
        String(50), default="chat", server_default="'chat'", comment="来源模块 chat/task_engine/agent"
    )
    action: Mapped[str] = mapped_column(
        String(80), default="", server_default="''",
        comment="动作名称 intent_recognize/case_review/script_gen/freeform_chat 等"
    )

    # ── 工具调用关联 ──
    tool_call_id: Mapped[str | None] = mapped_column(
        String(128), comment="工具调用 ID（关联 tool_call 与 tool_result）"
    )

    # ── 服务/模型 ──
    provider: Mapped[str] = mapped_column(
        String(50), default="", server_default="''", comment="供应商 deepseek/openai/local"
    )
    api_base: Mapped[str] = mapped_column(
        String(255), default="", server_default="''", comment="接口地址 base_url"
    )
    model: Mapped[str] = mapped_column(
        String(100), default="", server_default="''", comment="模型名称"
    )

    # ── 状态 ──
    status: Mapped[str] = mapped_column(
        String(20), default="success", server_default="'success'", comment="success/error/timeout"
    )
    error_msg: Mapped[str | None] = mapped_column(Text, comment="错误信息")

    # ── 请求/响应（核心排查数据）──
    request_messages: Mapped[list | dict | None] = mapped_column(
        JSONB, comment="请求 messages 完整 JSON（系统提示词 + 历史 + 用户输入）"
    )
    response_raw: Mapped[str | None] = mapped_column(Text, comment="LLM 原始返回文本")
    response_json: Mapped[dict | list | None] = mapped_column(
        JSONB, comment="LLM 结构化返回（JSON parse 后）"
    )

    # ── Token 用量（字段名与 DeepSeek usage 保持一致）──
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="输入 token 总数"
    )
    prompt_cache_hit_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="缓存命中 token（usage.prompt_cache_hit_tokens）"
    )
    prompt_cache_miss_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="缓存未命中 token（usage.prompt_cache_miss_tokens）"
    )
    prompt_cache_write_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="缓存写入 token（usage.prompt_cache_write_tokens）"
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="输出 token 总数"
    )
    reasoning_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="思考过程 token（reasoner 模型，usage.completion_tokens_details.reasoning_tokens）"
    )

    # ── 耗时 ──
    duration_ms: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="耗时(毫秒)"
    )

    # ── 时间 ──
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now(), comment="创建时间"
    )

    __table_args__ = (
        Index("idx_run_events_message", "message_id", "seq"),
        Index("idx_run_events_session", "session_id", "create_time"),
        Index("idx_run_events_time", "create_time"),
        Index("idx_run_events_model", "provider", "model"),
    )


class AiUsageDaily(Base, BaseIdMixin):
    """AI 按日用量汇总表 — 由定时任务从 ai_run_events 聚合生成。"""
    __tablename__ = "ai_usage_daily"

    stat_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="统计日期"
    )
    provider: Mapped[str] = mapped_column(
        String(50), default="", server_default="''", comment="供应商 deepseek/openai/local"
    )
    model: Mapped[str] = mapped_column(
        String(100), default="", server_default="''", comment="模型名称"
    )
    api_base: Mapped[str] = mapped_column(
        String(255), default="", server_default="''", comment="接口地址 base_url"
    )

    request_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="调用次数"
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="输入 token 总数"
    )
    prompt_cache_hit_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="缓存命中 token"
    )
    prompt_cache_miss_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="缓存未命中 token"
    )
    prompt_cache_write_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="缓存写入 token"
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="输出 token 总数"
    )
    reasoning_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="思考过程 token"
    )
    cost_cny: Mapped[float] = mapped_column(
        Numeric(14, 6), default=0, server_default="0", comment="费用（人民币）"
    )

    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now(), comment="创建时间"
    )

    __table_args__ = (
        UniqueConstraint("stat_date", "provider", "model", "api_base", name="uq_usage_daily_key"),
        Index("idx_usage_daily_date", "stat_date"),
    )
