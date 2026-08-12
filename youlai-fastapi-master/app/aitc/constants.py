"""测试部 AI 助手 — 常量、枚举与权限码。"""

from enum import Enum


# ── 用例重要性 ──

class CaseImportance(int, Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @classmethod
    def from_label(cls, label: str) -> int:
        label = label.strip()
        if label in ("高", "high", "3"):
            return cls.HIGH
        if label in ("低", "low", "1"):
            return cls.LOW
        return cls.MEDIUM

# ── 核心来源 ──

class CoreSource(int, Enum):
    AI = 1      # AI 挑选
    MANUAL = 2  # 人工标记

# ── 审核状态 ──

class ReviewStatus(int, Enum):
    UNREVIEWED = 0
    REVIEWED = 1

# ── 任务类型 ──

class TaskType(str, Enum):
    CORE_SELECT = "core_select"
    CASE_REVIEW = "case_review"
    SCRIPT_GEN = "script_gen"
    CASE_COMPLETE = "case_complete"

    @classmethod
    def labels(cls) -> dict:
        return {
            cls.CORE_SELECT: "挑选核心用例",
            cls.CASE_REVIEW: "用例审核",
            cls.SCRIPT_GEN: "生成测试脚本",
            cls.CASE_COMPLETE: "补全用例字段",
        }

# ── 提示词场景（同 TaskType） ──

# ── 样本类型 ──

class SampleType(str, Enum):
    CASE = "case"
    SCRIPT = "script"

# ── 任务状态 ──

class TaskStatus(int, Enum):
    QUEUED = 0       # 排队
    RUNNING = 1      # 运行中
    COMPLETED = 2    # 已完成
    FAILED = 3       # 失败
    CONFIRMED = 4    # 已确认
    STOPPED = 5      # 已停止

# ── 明细状态 ──

class ItemStatus(int, Enum):
    PENDING = 0
    SUCCESS = 1
    FAILED = 2

# ── 确认状态 ──

class ConfirmStatus(int, Enum):
    PENDING = 0          # 待确认
    ACCEPTED = 1         # 采纳
    IGNORED = 2          # 忽略
    EDITED_ACCEPTED = 3  # 编辑采纳

# ── 脚本来源 ──

class ScriptSource(int, Enum):
    AI = 1
    MANUAL = 2

# ── 脚本状态 ──

class ScriptStatus(int, Enum):
    DRAFT = 1     # 草稿
    PUBLISHED = 2 # 已入库

# ── 权限码 ──

PERM_PROJECT_LIST   = "aitc:project:list"
PERM_PROJECT_CREATE = "aitc:project:create"
PERM_PROJECT_UPDATE = "aitc:project:update"
PERM_PROJECT_DELETE = "aitc:project:delete"

PERM_CASE_LIST   = "aitc:case:list"
PERM_CASE_IMPORT = "aitc:case:import"
PERM_CASE_UPDATE = "aitc:case:update"
PERM_CASE_DELETE = "aitc:case:delete"
PERM_CASE_CORE   = "aitc:case:core"
PERM_CASE_SAMPLE = "aitc:case:sample"

PERM_SAMPLE_LIST   = "aitc:sample:list"
PERM_SAMPLE_CREATE = "aitc:sample:create"
PERM_SAMPLE_UPDATE = "aitc:sample:update"
PERM_SAMPLE_DELETE = "aitc:sample:delete"

PERM_TASK_CREATE  = "aitc:task:create"
PERM_TASK_LIST    = "aitc:task:list"
PERM_TASK_CONFIRM = "aitc:task:confirm"
PERM_TASK_STOP    = "aitc:task:stop"

PERM_SCRIPT_LIST   = "aitc:script:list"
PERM_SCRIPT_UPDATE = "aitc:script:update"
PERM_SCRIPT_EXPORT = "aitc:script:export"

PERM_SPEC_LIST   = "aitc:spec:list"
PERM_SPEC_CREATE = "aitc:spec:create"
PERM_SPEC_UPDATE = "aitc:spec:update"
PERM_SPEC_DELETE = "aitc:spec:delete"

PERM_SYNONYM_LIST   = "aitc:retrieval:synonym:list"
PERM_SYNONYM_CREATE = "aitc:retrieval:synonym:create"
PERM_SYNONYM_UPDATE = "aitc:retrieval:synonym:update"
PERM_SYNONYM_DELETE = "aitc:retrieval:synonym:delete"
PERM_SYNONYM_SYNC   = "aitc:retrieval:synonym:sync"

# ── 规范类型 ──

class SpecType(str, Enum):
    GENERAL = "general"                    # 通用规范
    MODULE_SPECIFIC = "module_specific"    # 各模块专用规范
    COMMON_ISSUES = "common_issues"        # 常见问题

    @classmethod
    def labels(cls) -> dict:
        return {
            cls.GENERAL: "通用规范",
            cls.MODULE_SPECIFIC: "各模块专用规范",
            cls.COMMON_ISSUES: "常见问题",
        }


