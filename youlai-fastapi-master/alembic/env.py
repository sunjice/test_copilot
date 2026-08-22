"""Alembic environment configuration.

Supports SQLAlchemy 2.0 ORM (DeclarativeBase). Reads DATABASE_URL
dynamically from app.config.settings (pydantic-settings).

Sync psycopg2 is used for migrations (more robust than asyncpg
for Alembic DDL execution).
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make project root importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402

# IMPORTANT: import every module that defines ORM models so Base.metadata
# collects them. When adding a new ORM model module, add its import here.
# Pattern: from app.<pkg>.<subpkg> import models   (must reach models.py)
from app.system.user import models as sys_user_models  # noqa: F401,E402
from app.system.role import models as sys_role_models  # noqa: F401,E402
from app.system.dept import models as sys_dept_models  # noqa: F401,E402
from app.system.menu import models as sys_menu_models  # noqa: F401,E402
from app.system.dict import models as sys_dict_models  # noqa: F401,E402
from app.system.config import models as sys_config_models  # noqa: F401,E402
from app.system.log import models as sys_log_models  # noqa: F401,E402
from app.system.notice import models as sys_notice_models  # noqa: F401,E402

from app.aitc import models as aitc_models  # noqa: F401,E402
from app.aitc.case import models as aitc_case_models  # noqa: F401,E402
from app.aitc.sample import models as aitc_sample_models  # noqa: F401,E402
from app.aitc.script import models as aitc_script_models  # noqa: F401,E402
from app.aitc.spec import models as aitc_spec_models  # noqa: F401,E402
from app.aitc.task import models as aitc_task_models  # noqa: F401,E402
from app.aitc.testlink import models as aitc_testlink_models  # noqa: F401,E402

from app.ai.llm_log import models as llm_log_models  # noqa: F401,E402
from app.ai.chat import models as chat_models  # noqa: F401,E402


config = context.config

# Resolve DSN. Priority:
#   1. ALEMBIC_DATABASE_URL env var (sync DSN; for new servers)
#   2. APP DATABASE_URL (async); convert asyncpg -> psycopg2
db_url = os.environ.get("ALEMBIC_DATABASE_URL") or settings.DATABASE_URL
if db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline mode: emit SQL to stdout/file without connecting."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online mode: connect and execute DDL."""
    cfg_section = config.get_section(config.config_ini_section) or {}
    cfg_section = {**cfg_section, "sqlalchemy.url": db_url}

    connectable = engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
