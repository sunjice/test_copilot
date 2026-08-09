/**
 * AITC 枚举定义（与后端 app/system/aitc/constants.py 同步）
 */

// ── 任务类型 ──
export enum TaskTypeEnum {
  CORE_SELECT = 'core_select',
  CASE_REVIEW = 'case_review',
  SCRIPT_GEN = 'script_gen',
  CASE_COMPLETE = 'case_complete',
}

// ── 任务状态 ──
export enum TaskStatusEnum {
  QUEUED = 0,
  RUNNING = 1,
  COMPLETED = 2,
  FAILED = 3,
  CONFIRMED = 4,
  STOPPED = 5,
}

// ── 子任务状态 ──
export enum ItemStatusEnum {
  PENDING = 0,
  SUCCESS = 1,
  FAILED = 2,
}

// ── 确认状态 ──
export enum ConfirmStatusEnum {
  PENDING = 0,
  ACCEPTED = 1,
  IGNORED = 2,
  EDIT_ACCEPTED = 3,
}

// ── 用例重要程度 ──
export enum CaseImportanceEnum {
  LOW = 1,
  MEDIUM = 2,
  HIGH = 3,
}

// ── 核心来源 ──
export enum CoreSourceEnum {
  AI = 1,
  MANUAL = 2,
}

// ── 审核状态 ──
export enum ReviewStatusEnum {
  UNREVIEWED = 0,
  REVIEWED = 1,
}

// ── 审核动作 ──
export enum ReviewActionEnum {
  ACCEPT = 'accept',
  IGNORE = 'ignore',
  EDIT_ACCEPT = 'edit_accept',
}

// ── 脚本来源 ──
export enum ScriptSourceEnum {
  AI = 1,
  MANUAL = 2,
}

// ── 脚本状态 ──
export enum ScriptStatusEnum {
  DRAFT = 1,
  PUBLISHED = 2,
}

// ── 样本类型 ──
export enum SampleTypeEnum {
  CASE = 'case',
  SCRIPT = 'script',
}

// ── 规范类型 ──
export enum SpecTypeEnum {
  GENERAL = 'general',
  MODULE_SPECIFIC = 'module_specific',
  COMMON_ISSUES = 'common_issues',
}
