"""用例域 — ORM 模型（Project / Suite / Case）。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, BaseIdMixin, SoftDeleteMixin, TimestampMixin


class AiTcProject(Base, BaseIdMixin, TimestampMixin, SoftDeleteMixin):
    """测试项目（用例集 / 产品）。"""
    __tablename__ = "ai_tc_projects"

    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="项目名称")
    prefix: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="项目标识")
    description: Mapped[str | None] = mapped_column(Text, comment="项目描述")
    testlink_project_id: Mapped[int | None] = mapped_column(BigInteger, comment="TestLink testproject id")
    last_sync_time: Mapped[str | None] = mapped_column(String(32), comment="最后导入时间")

    suites: Mapped[list["AiTcSuite"]] = relationship(
        back_populates="project", lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("prefix", name="uq_aitc_project_prefix"),
    )


class AiTcSuite(Base, BaseIdMixin, TimestampMixin, SoftDeleteMixin):
    """测试套件（模块树节点）。"""
    __tablename__ = "ai_tc_suites"

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ai_tc_projects.id"), nullable=False, comment="项目ID"
    )
    parent_id: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", comment="父套件ID，0 为根"
    )
    tree_path: Mapped[str] = mapped_column(String(512), default="", server_default="", comment="祖先路径如 0,1,5")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="套件名称")
    description: Mapped[str | None] = mapped_column(Text, comment="套件描述")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="排序")
    testlink_suite_id: Mapped[int | None] = mapped_column(BigInteger, comment="TestLink testsuite id")

    project: Mapped["AiTcProject"] = relationship(back_populates="suites", lazy="selectin")
    cases: Mapped[list["AiTcCase"]] = relationship(back_populates="suite", lazy="selectin")

    __table_args__ = (
        Index("idx_aitc_suite_project", "project_id", "is_deleted"),
        Index("idx_aitc_suite_parent", "parent_id"),
        Index("idx_aitc_suite_tree", "tree_path"),
    )


class AiTcCase(Base, BaseIdMixin, TimestampMixin, SoftDeleteMixin):
    """测试用例。"""
    __tablename__ = "ai_tc_cases"

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ai_tc_projects.id"), nullable=False, comment="项目ID"
    )
    suite_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ai_tc_suites.id"), nullable=False, comment="所属套件ID"
    )
    external_id: Mapped[str | None] = mapped_column(String(64), comment="TestLink用例编号，项目内唯一（如 001）")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="英文标识名（如 ssid_name_length_check）")
    purpose: Mapped[str | None] = mapped_column(String(256), comment="测试目的 / 中文用例名称（如 SSID长度验证）")
    summary: Mapped[str | None] = mapped_column(Text, comment="测试思想")
    preconditions: Mapped[str | None] = mapped_column(Text, comment="前置条件")
    topo: Mapped[str | None] = mapped_column(String(512), comment="测试Topo")
    test_data: Mapped[str | None] = mapped_column(Text, comment="测试数据")
    steps: Mapped[list | None] = mapped_column(JSONB, comment="测试步骤 [{action, expected, step_no}]")
    importance: Mapped[int] = mapped_column(
        SmallInteger, default=2, server_default="2", comment="级别 1-低 2-中 3-高"
    )
    is_core: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", comment="是否核心用例 0-否 1-是"
    )
    core_reason: Mapped[str | None] = mapped_column(String(512), comment="标记为核心的原因")
    core_source: Mapped[int | None] = mapped_column(
        SmallInteger, comment="核心来源 1-AI挑选 2-人工标记"
    )
    is_sample: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", comment="是否样本用例 0-否 1-是"
    )
    review_status: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", comment="审核状态 0-未审核 1-已审核"
    )
    script_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="关联脚本数量（冗余计数）"
    )

    # ── TestLink 身份映射 ──
    testlink_tc_id: Mapped[int | None] = mapped_column(BigInteger, comment="TestLink 内部 testcase_id")
    testlink_version_id: Mapped[int | None] = mapped_column(BigInteger, comment="TestLink tcversion_id（每次远端编辑会变）")

    # ── 同步状态与控制 ──
    sync_status: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0",
        comment="同步状态 0-未关联 1-已同步 2-待反写 3-远端有更新 4-冲突 5-反写失败 6-远端已删除"
    )
    synced_version: Mapped[int | None] = mapped_column(Integer, comment="上次同步时的 TestLink version")
    synced_hash: Mapped[str | None] = mapped_column(String(64), comment="上次同步内容的 SHA256（本地脏检测基准）")
    synced_snapshot: Mapped[dict | None] = mapped_column(JSONB, comment="上次同步时的字段快照（三方合并用）")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, comment="上次同步时间")
    last_push_at: Mapped[datetime | None] = mapped_column(DateTime, comment="上次反写时间")
    testlink_modified_at: Mapped[datetime | None] = mapped_column(DateTime, comment="TestLink 端 modification_ts")
    testlink_modifier: Mapped[str | None] = mapped_column(String(128), comment="TestLink 端最后修改人")
    auto_sync: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="修改后是否自动反写 0-否 1-是"
    )
    sync_error: Mapped[str | None] = mapped_column(Text, comment="最近一次反写失败原因")

    # ── TestLink 原文（HTML 富文本，双轨：原文存库 + 清洗字段消费）──
    summary_raw: Mapped[str | None] = mapped_column(Text, comment="测试思想的原始 HTML")
    preconditions_raw: Mapped[str | None] = mapped_column(Text, comment="前置条件的原始 HTML")
    steps_raw: Mapped[str | None] = mapped_column(Text, comment="测试步骤的原始 HTML（整段）")
    test_data_raw: Mapped[str | None] = mapped_column(Text, comment="测试数据的原始 HTML")
    steps_parse_status: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0",
        comment="步骤结构化解析状态 0-未解析 1-解析成功 2-解析降级为纯文本"
    )

    # ── 检索引擎追踪 ──
    index_hash: Mapped[str | None] = mapped_column(String(64), comment="索引内容 SHA256，用于增量变更检测")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="最近一次索引时间")

    suite: Mapped["AiTcSuite"] = relationship(back_populates="cases", lazy="selectin")
    project: Mapped["AiTcProject"] = relationship(lazy="selectin")
    scripts: Mapped[list["AiTcScript"]] = relationship(back_populates="case", lazy="selectin")

    __table_args__ = (
        Index("idx_aitc_case_suite", "suite_id", "is_deleted"),
        Index("idx_aitc_case_project_core", "project_id", "is_core"),
        Index("idx_aitc_case_review", "project_id", "review_status"),
        Index("idx_aitc_case_tl_tc", "testlink_tc_id"),
        Index("idx_aitc_case_sync_status", "project_id", "sync_status"),
        UniqueConstraint("project_id", "external_id", name="uq_aitc_case_extid"),
    )
