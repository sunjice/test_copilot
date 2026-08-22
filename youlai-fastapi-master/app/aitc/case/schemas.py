"""用例域 — Pydantic Schemas（项目/套件/用例/审核/导入）。"""

from typing import Any

from pydantic import BaseModel, Field

from app.pagination import PageQuery
from app.serializers import BigId


# ═══════════════ 项目 ═══════════════

class ProjectQuery(PageQuery):
    keywords: str | None = Field(default=None, description="搜索关键词")


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="项目名称")
    prefix: str = Field(..., min_length=1, max_length=64, description="项目标识")
    description: str | None = Field(default=None, description="项目描述")


class ProjectUpdate(ProjectCreate):
    id: BigId | None = Field(default=None, description="项目ID")


class ProjectVO(BaseModel):
    id: BigId | None = None
    name: str = ""
    prefix: str = ""
    description: str | None = None
    last_sync_time: str | None = None
    create_time: str | None = None
    update_time: str | None = None
    model_config = {"from_attributes": True}


# ═══════════════ 套件树 ═══════════════

class SuiteNodeVO(BaseModel):
    """套件树节点（供 el-tree），node_type 区分套件(module)和用例(case)。"""
    id: BigId
    label: str
    name: str = ""
    description: str | None = None
    project_id: BigId | None = None
    project_prefix: str = ""
    parent_id: BigId = 0
    sort_order: int = 0
    case_count: int = 0
    node_type: str = "suite"  # suite | case
    external_id: str | None = None  # 仅 case 节点有值（用例编号）
    children: list["SuiteNodeVO"] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class SuiteVO(BaseModel):
    id: BigId | None = None
    project_id: BigId | None = None
    parent_id: BigId = 0
    tree_path: str = ""
    name: str = ""
    description: str | None = None
    sort_order: int = 0
    create_time: str | None = None
    update_time: str | None = None
    model_config = {"from_attributes": True}


# ═══════════════ 用例 ═══════════════

class CaseStep(BaseModel):
    """测试步骤。"""
    step_no: int = 0
    action: str = ""
    expected: str = ""


class CaseQuery(PageQuery):
    projectId: BigId | None = Field(default=None, description="项目ID")
    suiteId: BigId | None = Field(default=None, description="套件ID（含子树）")
    isCore: int | None = Field(default=None, description="是否核心 0/1")
    isSample: int | None = Field(default=None, description="是否样本 0/1")
    reviewStatus: int | None = Field(default=None, description="审核状态 0/1")
    importance: int | None = Field(default=None, description="级别 1/2/3")
    keywords: str | None = Field(default=None, description="搜索关键词")
    sortField: str | None = Field(default=None, description="排序字段")
    sortOrder: str | None = Field(default=None, description="排序方向 ascending/descending")


class CaseVO(BaseModel):
    """用例列表行 / 详情。"""
    id: BigId | None = None
    project_id: BigId | None = None
    project_prefix: str = ""
    suite_id: BigId | None = None
    suite_name: str = ""
    external_id: str | None = None
    name: str = ""
    purpose: str | None = None
    summary: str | None = None
    preconditions: str | None = None
    topo: str | None = None
    test_data: str | None = None
    steps: list[CaseStep] = Field(default_factory=list)
    # ── TestLink 原文（HTML 富文本），前端 v-html 渲染 ──
    summary_raw: str | None = None
    preconditions_raw: str | None = None
    steps_raw: str | None = None
    test_data_raw: str | None = None
    steps_parse_status: int = 0
    importance: int = 2
    is_core: int = 0
    core_reason: str | None = None
    core_source: int | None = None
    is_sample: int = 0
    review_status: int = 0
    script_count: int = 0
    create_time: str | None = None
    update_time: str | None = None
    model_config = {"from_attributes": True}


class CaseUpdate(BaseModel):
    """人工编辑用例。"""
    external_id: str | None = Field(default=None, max_length=64, description="用例编号")
    name: str = Field(..., min_length=1, max_length=256)
    purpose: str | None = Field(default=None, max_length=256, description="测试目的/中文用例名称")
    summary: str | None = None
    preconditions: str | None = None
    topo: str | None = None
    test_data: str | None = None
    steps: list[CaseStep] = Field(default_factory=list)
    importance: int = 2


class CaseCoreMark(BaseModel):
    """人工标记/取消核心。"""
    case_id: BigId = Field(..., description="用例ID")
    is_core: int = Field(..., description="0/1")
    reason: str | None = Field(default=None, max_length=512)


class CaseSampleMark(BaseModel):
    """人工标记/取消样本。"""
    case_id: BigId = Field(..., description="用例ID")
    is_sample: int = Field(..., description="0/1")


# ═══════════════ Excel 导入 ═══════════════

class ImportResult(BaseModel):
    """Excel 导入结果。"""
    created: int = 0
    updated: int = 0
    errors: list[dict] = Field(default_factory=list)  # [{row, msg}]


# ═══════════════ 用例审核工作台 ═══════════════

class PendingSuiteNodeVO(BaseModel):
    """套件树节点（含待审核计数）。"""
    id: BigId
    label: str
    name: str = ""
    description: str | None = None
    project_id: BigId | None = None
    parent_id: BigId = 0
    sort_order: int = 0
    case_count: int = 0
    pending_count: int = 0
    children: list["PendingSuiteNodeVO"] = Field(default_factory=list)
    cases: list["PendingCaseVO"] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class PendingCaseVO(BaseModel):
    """待审核用例摘要。"""
    id: BigId
    external_id: str | None = None
    name: str = ""
    importance: int = 2


class FieldSuggestionVO(BaseModel):
    """单个字段的 AI 修改建议。"""
    field_name: str = ""
    original: Any | None = None
    suggested: Any | None = None
    has_suggestion: bool = False
    conclusion: str = ""        # pass / fail
    rule_violated: str = ""     # 违反的规范说明


class CaseReviewDetailVO(BaseModel):
    """用例审核详情（原用例 + AI 建议）。"""
    case: CaseVO | None = None
    task_item_id: BigId | None = None
    task_id: BigId | None = None
    score: int | None = None
    issues: list[str] = Field(default_factory=list)
    suggestions: list[FieldSuggestionVO] = Field(default_factory=list)
    overall_assessment: str = ""  # 整体评价


class CaseFieldReviewItem(BaseModel):
    """逐字段审核结果。"""
    field_name: str = Field(..., description="字段名")
    action: str = Field(..., description="accept/ignore")
    edited_value: Any | None = None


class CaseReviewReq(BaseModel):
    """提交用例审核请求。"""
    case_id: BigId
    task_item_id: BigId
    fields: list[CaseFieldReviewItem] = Field(default_factory=list)
