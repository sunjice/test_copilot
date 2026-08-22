"""add testlink raw html fields to ai_tc_cases

Revision ID: 3c4d5e6f7a8b
Revises: 2a3b4c5d6e7f
Create Date: 2026-08-17 00:00:00.000000

新增 TestLink 原文（HTML）双轨字段：
    summary_raw / preconditions_raw / steps_raw / test_data_raw / steps_parse_status
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c4d5e6f7a8b"
down_revision: Union[str, None] = "2a3b4c5d6e7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_tc_cases", sa.Column("summary_raw", sa.Text(), nullable=True, comment="测试思想的原始 HTML"))
    op.add_column("ai_tc_cases", sa.Column("preconditions_raw", sa.Text(), nullable=True, comment="前置条件的原始 HTML"))
    op.add_column("ai_tc_cases", sa.Column("steps_raw", sa.Text(), nullable=True, comment="测试步骤的原始 HTML（整段）"))
    op.add_column("ai_tc_cases", sa.Column("test_data_raw", sa.Text(), nullable=True, comment="测试数据的原始 HTML"))
    op.add_column(
        "ai_tc_cases",
        sa.Column(
            "steps_parse_status",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
            comment="步骤结构化解析状态 0-未解析 1-解析成功 2-解析降级为纯文本",
        ),
    )

    # 新建同步审计表 ai_tc_sync_logs
    op.create_table(
        "ai_tc_sync_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键ID"),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("ai_tc_projects.id"), nullable=False, comment="项目ID"),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("ai_tc_cases.id"), nullable=True, comment="用例ID"),
        sa.Column("direction", sa.String(16), nullable=False, comment="方向 pull/push"),
        sa.Column("action", sa.String(32), nullable=False, comment="操作 sync/push_case/conflict 等"),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1", comment="结果 0-失败 1-成功"),
        sa.Column("testlink_tc_id", sa.String(64), nullable=True, comment="TestLink 用例 ID"),
        sa.Column("detail", sa.Text(), nullable=True, comment="详情/错误信息"),
        sa.Column("operator", sa.String(64), nullable=True, comment="操作人"),
        sa.Column("operated_at", sa.DateTime(), nullable=True, comment="操作时间"),
        sa.Column("create_time", sa.DateTime(), nullable=True, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=True, comment="更新时间"),
    )
    op.create_index("idx_aitc_synclog_project", "ai_tc_sync_logs", ["project_id"])
    op.create_index("idx_aitc_synclog_case", "ai_tc_sync_logs", ["case_id"])
    op.create_index("idx_aitc_synclog_direction", "ai_tc_sync_logs", ["direction", "status"])


def downgrade() -> None:
    op.drop_table("ai_tc_sync_logs")
    op.drop_column("ai_tc_cases", "steps_parse_status")
    op.drop_column("ai_tc_cases", "test_data_raw")
    op.drop_column("ai_tc_cases", "steps_raw")
    op.drop_column("ai_tc_cases", "preconditions_raw")
    op.drop_column("ai_tc_cases", "summary_raw")
