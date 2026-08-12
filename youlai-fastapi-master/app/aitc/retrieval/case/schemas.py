"""用例检索引擎 — Pydantic 模型。"""

from pydantic import BaseModel, Field


class CaseIndexData(BaseModel):
    """待索引的用例数据（标准化结构）。"""
    case_id: int
    project_id: int
    suite_id: int
    name: str
    purpose: str = ""
    summary: str = ""
    steps_text: str = ""       # 已清洗的纯文本步骤
    topo: str = ""
    importance: int = 2
    is_core: bool = False
    is_sample: bool = False
    is_deleted: bool = False
    updated_at: str = ""  # ISO 格式时间戳
    # 追踪
    index_hash: str = ""


class IndexProgress(BaseModel):
    """索引进度。"""
    total: int = 0
    indexed: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
