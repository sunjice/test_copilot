"""TestLink 同步审计表 + 同步相关 Pydantic 模型。

- AiTcSyncLog: 同步/反写操作审计日志（记录每次操作的用例、方向、结果、错误）
- Pydantic 模型: 同步/反写请求与结果（router 用）
"""

from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BaseIdMixin, TimestampMixin


# ════════════════════════════════════════════
# ORM：同步审计表
# ════════════════════════════════════════════

class AiTcSyncLog(Base, BaseIdMixin, TimestampMixin):
    """TestLink 同步/反写审计日志。"""

    __tablename__ = "ai_tc_sync_logs"

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ai_tc_projects.id"), nullable=False, comment="项目ID"
    )
    case_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ai_tc_cases.id"), comment="用例ID（全量同步等无单用例时为 NULL）"
    )
    direction: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="方向 pull(拉取) / push(反写)"
    )
    action: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="操作 sync(同步) / push_case(反写) / conflict(冲突) 等"
    )
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="结果 0-失败 1-成功"
    )
    testlink_tc_id: Mapped[str | None] = mapped_column(
        String(64), comment="TestLink 用例 ID（如 C-2185677）"
    )
    detail: Mapped[str | None] = mapped_column(Text, comment="详情/错误信息")
    operator: Mapped[str | None] = mapped_column(String(64), comment="操作人（定时任务为 system）")
    operated_at: Mapped[datetime | None] = mapped_column(DateTime, comment="操作时间")

    __table_args__ = (
        Index("idx_aitc_synclog_project", "project_id"),
        Index("idx_aitc_synclog_case", "case_id"),
        Index("idx_aitc_synclog_direction", "direction", "status"),
    )


# ════════════════════════════════════════════
# Pydantic 模型（router 请求/响应）
# ════════════════════════════════════════════

class SyncRequest(BaseModel):
    """手动触发全量同步请求。"""

    project_id: int = Field(..., description="本地项目ID")


class PushRequest(BaseModel):
    """手动触发反写请求。"""

    project_id: int = Field(..., description="本地项目ID")
    case_ids: list[int] | None = Field(default=None, description="指定用例，为空则反写所有待反写用例")


class SyncStats(BaseModel):
    """同步/反写统计结果。"""

    suites_created: int = 0
    suites_updated: int = 0
    cases_created: int = 0
    cases_updated: int = 0
    cases_deleted: int = 0
    conflicts: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
