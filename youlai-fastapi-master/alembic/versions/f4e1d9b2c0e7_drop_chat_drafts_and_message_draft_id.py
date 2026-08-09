"""drop chat_drafts table and chat_messages.draft_id

Revision ID: f4e1d9b2c0e7
Revises: 11eff7563164
Create Date: 2026-08-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f4e1d9b2c0e7'
down_revision: Union[str, None] = '11eff7563164'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('chat_drafts')
    op.drop_column('chat_messages', 'draft_id')


def downgrade() -> None:
    op.add_column('chat_messages', sa.Column('draft_id', sa.BigInteger(), nullable=True, comment='关联的 Draft ID（如有产出）'))
    op.create_table('chat_drafts',
        sa.Column('session_id', sa.BigInteger(), nullable=False, comment='所属会话ID'),
        sa.Column('message_id', sa.BigInteger(), nullable=False, comment='关联消息ID'),
        sa.Column('draft_type', sa.String(length=30), nullable=False, comment='草稿类型 core_select/case_review/script_gen/field_complete/steps_complete/case_design'),
        sa.Column('title', sa.String(length=200), server_default='', nullable=False, comment='草稿标题'),
        sa.Column('content_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='草稿内容'),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False, comment='状态 pending/confirmed/applied/discarded'),
        sa.Column('confirmed_by', sa.String(length=64), nullable=True, comment='确认人'),
        sa.Column('confirmed_at', sa.String(length=32), nullable=True, comment='确认时间'),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('create_time', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
        sa.Column('update_time', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_chat_draft_msg', 'chat_drafts', ['message_id'], unique=False)
    op.create_index('idx_chat_draft_session', 'chat_drafts', ['session_id'], unique=False)
