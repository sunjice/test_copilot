"""检索域 — 业务 Pydantic 模型（同义词管理等，供前端页面使用）。"""

from pydantic import BaseModel, Field


class SynonymCreate(BaseModel):
    """新增同义词词条。"""
    synonym_group: str = Field(..., min_length=1, max_length=128, description="同义词组标识，同组词条可互相替换")
    term: str = Field(..., min_length=1, max_length=256, description="术语词条")
    domain: str = Field(default="", max_length=64, description="适用领域，留空表示全局")
    is_preferred: bool = Field(default=False, description="是否首选词")


class SynonymUpdate(BaseModel):
    """更新同义词词条（仅更新传入字段）。"""
    synonym_group: str | None = Field(default=None, min_length=1, max_length=128, description="同义词组标识")
    term: str | None = Field(default=None, min_length=1, max_length=256, description="术语词条")
    domain: str | None = Field(default=None, max_length=64, description="适用领域")
    is_preferred: bool | None = Field(default=None, description="是否首选词")


class SynonymItem(BaseModel):
    """同义词词条（列表展示）。"""
    id: int
    synonym_group: str
    term: str
    is_preferred: bool = False
    domain: str = ""
    created_at: str | None = None
    updated_at: str | None = None
