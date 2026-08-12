"""baseline: 真实库当前状态（与 sql/*.sql 同步）。

Revision ID: 11eff7563164
Revises:
Create Date: 2026-08-12 19:00:00.000000

说明
----
本迁移为 alembic 基线（baseline）。

- 历史背景：SQL 文件（sql/postgresql/youlai-admin.sql + youlai-aitc.sql）
  描述了真实库（localhost:15432/youlai_admin, PostgreSQL 16）当前结构。
- 真实库的 alembic_version 此前指向 11eff7563164（旧迁移已删除），
  此迁移以同一 revision id 重启，标记"库结构等于 SQL 快照"。

后续开发改 ORM 后，从本迁移作为 head 通过
``alembic revision --autogenerate -m "..."`` 生成增量迁移即可。

首次上线流程
----------
新服务器执行：
    psql -f sql/postgresql/youlai-admin.sql
    psql -f sql/postgresql/youlai-aitc.sql
    alembic stamp 11eff7563164
"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "11eff7563164"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: 库结构已由 SQL 文件建立。"""
    pass


def downgrade() -> None:
    """No-op: 基线无前置状态。"""
    pass
