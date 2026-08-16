"""add ai_run_events and ai_usage_daily, drop ai_llm_logs and ai_usage_logs

Revision ID: 2a3b4c5d6e7f
Revises: 11eff7563164
Create Date: 2026-08-16 12:00:00.000000

说明
----
- 新建 ``ai_run_events``（平铺轨迹 + token 用量，字段对齐 DeepSeek usage）
- 新建 ``ai_usage_daily``（每日用量汇总）
- 删除旧表 ``ai_llm_logs``、``ai_usage_logs``（项目未上线，不保留旧日志）
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2a3b4c5d6e7f"
down_revision: Union[str, None] = "11eff7563164"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 新建 ai_run_events ──
    op.create_table(
        "ai_run_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column("event_type", sa.String(40), server_default="'llm_call'", nullable=False),
        sa.Column("module", sa.String(50), server_default="'chat'", nullable=False),
        sa.Column("action", sa.String(80), server_default="''", nullable=False),
        sa.Column("tool_call_id", sa.String(128), nullable=True),
        sa.Column("provider", sa.String(50), server_default="''", nullable=False),
        sa.Column("api_base", sa.String(255), server_default="''", nullable=False),
        sa.Column("model", sa.String(100), server_default="''", nullable=False),
        sa.Column("status", sa.String(20), server_default="'success'", nullable=False),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("request_messages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_raw", sa.Text(), nullable=True),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("prompt_cache_hit_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("prompt_cache_miss_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("prompt_cache_write_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reasoning_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "create_time",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_run_events_message", "ai_run_events", ["message_id", "seq"])
    op.create_index("idx_run_events_session", "ai_run_events", ["session_id", "create_time"])
    op.create_index("idx_run_events_time", "ai_run_events", ["create_time"])
    op.create_index("idx_run_events_model", "ai_run_events", ["provider", "model"])

    # ── 新建 ai_usage_daily ──
    op.create_table(
        "ai_usage_daily",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stat_date", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(50), server_default="''", nullable=False),
        sa.Column("model", sa.String(100), server_default="''", nullable=False),
        sa.Column("api_base", sa.String(255), server_default="''", nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("prompt_cache_hit_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("prompt_cache_miss_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("prompt_cache_write_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reasoning_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_cny", sa.Numeric(14, 6), server_default="0", nullable=False),
        sa.Column(
            "create_time",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "stat_date", "provider", "model", "api_base", name="uq_usage_daily_key"
        ),
    )
    op.create_index("idx_usage_daily_date", "ai_usage_daily", ["stat_date"])

    # ── 删除旧表（项目未上线，不保留旧日志）──
    op.drop_index("idx_llm_log_session", table_name="ai_llm_logs")
    op.drop_index("idx_llm_log_trace", table_name="ai_llm_logs")
    op.drop_index("idx_llm_log_status", table_name="ai_llm_logs")
    op.drop_index("idx_llm_log_action", table_name="ai_llm_logs")
    op.drop_table("ai_llm_logs")

    op.drop_index("idx_usage_module", table_name="ai_usage_logs")
    op.drop_index("idx_usage_session", table_name="ai_usage_logs")
    op.drop_table("ai_usage_logs")


def downgrade() -> None:
    # 恢复旧表
    op.create_table(
        "ai_usage_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("module", sa.String(50), server_default="'chat'", nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column("task_id", sa.BigInteger(), nullable=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_usage_module", "ai_usage_logs", ["module", "created_at"])
    op.create_index("idx_usage_session", "ai_usage_logs", ["session_id"])

    op.create_table(
        "ai_llm_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(128), server_default="''", nullable=False),
        sa.Column("span_seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("module", sa.String(50), server_default="'chat'", nullable=False),
        sa.Column("action", sa.String(80), server_default="''", nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column("task_id", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("model", sa.String(100), server_default="''", nullable=False),
        sa.Column("status", sa.String(20), server_default="'success'", nullable=False),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_raw", sa.Text(), nullable=True),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "create_time",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_llm_log_session", "ai_llm_logs", ["session_id", "create_time"])
    op.create_index("idx_llm_log_trace", "ai_llm_logs", ["trace_id"])
    op.create_index("idx_llm_log_status", "ai_llm_logs", ["status", "create_time"])
    op.create_index("idx_llm_log_action", "ai_llm_logs", ["action"])

    op.drop_index("idx_usage_daily_date", table_name="ai_usage_daily")
    op.drop_table("ai_usage_daily")

    op.drop_index("idx_run_events_model", table_name="ai_run_events")
    op.drop_index("idx_run_events_time", table_name="ai_run_events")
    op.drop_index("idx_run_events_session", table_name="ai_run_events")
    op.drop_index("idx_run_events_message", table_name="ai_run_events")
    op.drop_table("ai_run_events")
