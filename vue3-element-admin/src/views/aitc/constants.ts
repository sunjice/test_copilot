/**
 * AITC 全局常量（标签/颜色映射，全局唯一来源）
 */
import {
  TaskTypeEnum, TaskStatusEnum, ItemStatusEnum, ConfirmStatusEnum,
  CaseImportanceEnum, CoreSourceEnum, ReviewActionEnum,
  ScriptSourceEnum, ScriptStatusEnum, SampleTypeEnum, SpecTypeEnum,
} from '@/enums/aitc'

// ── 任务类型 标签/颜色 ──
export const TASK_TYPE_MAP: Record<string, { label: string; tag: string }> = {
  [TaskTypeEnum.CORE_SELECT]: { label: '挑核心', tag: 'success' },
  [TaskTypeEnum.CASE_REVIEW]: { label: '用例审核', tag: 'warning' },
  [TaskTypeEnum.SCRIPT_GEN]: { label: '生成脚本', tag: '' },
  [TaskTypeEnum.CASE_COMPLETE]: { label: '完善用例', tag: '' },
}

export function taskTypeLabel(type: string): string {
  return TASK_TYPE_MAP[type]?.label ?? type
}

export function taskTypeTag(type: string): string {
  return TASK_TYPE_MAP[type]?.tag || 'info'
}

// ── 任务状态 标签/颜色 ──
export const TASK_STATUS_MAP: Record<number, { label: string; tag: string }> = {
  [TaskStatusEnum.QUEUED]:    { label: '排队中', tag: 'info' },
  [TaskStatusEnum.RUNNING]:   { label: '运行中', tag: 'warning' },
  [TaskStatusEnum.COMPLETED]: { label: '已完成', tag: 'success' },
  [TaskStatusEnum.FAILED]:    { label: '失败',   tag: 'danger' },
  [TaskStatusEnum.CONFIRMED]: { label: '已确认', tag: 'success' },
  [TaskStatusEnum.STOPPED]:   { label: '已停止', tag: 'info' },
}

export function statusLabel(status: number): string {
  return TASK_STATUS_MAP[status]?.label ?? `未知(${status})`
}

export function statusTag(status: number): string {
  return TASK_STATUS_MAP[status]?.tag ?? 'info'
}

// ── 确认状态 标签/颜色 ──
export const CONFIRM_STATUS_MAP: Record<number, { label: string; tag: string }> = {
  [ConfirmStatusEnum.PENDING]:       { label: '待确认', tag: 'info' },
  [ConfirmStatusEnum.ACCEPTED]:      { label: '采纳',   tag: 'success' },
  [ConfirmStatusEnum.IGNORED]:       { label: '忽略',   tag: '' },
  [ConfirmStatusEnum.EDIT_ACCEPTED]: { label: '编辑采纳', tag: 'success' },
}

export function confirmLabel(status: number): string {
  return CONFIRM_STATUS_MAP[status]?.label ?? `未知(${status})`
}

export function confirmTag(status: number): string {
  return CONFIRM_STATUS_MAP[status]?.tag ?? 'info'
}

// ── 审核动作 标签/颜色 ──
export const REVIEW_ACTION_MAP: Record<string, { label: string; tag: string }> = {
  [ReviewActionEnum.ACCEPT]:      { label: '采纳', tag: 'success' },
  [ReviewActionEnum.IGNORE]:      { label: '忽略', tag: 'info' },
  [ReviewActionEnum.EDIT_ACCEPT]: { label: '编辑采纳', tag: 'warning' },
}

export function reviewActionLabel(action: string): string {
  return REVIEW_ACTION_MAP[action]?.label ?? action
}

export function reviewActionTag(action: string): string {
  return REVIEW_ACTION_MAP[action]?.tag ?? ''
}

// ── 用例重要程度 标签/颜色 ──
export const IMPORTANCE_MAP: Record<number, { label: string; type: string }> = {
  [CaseImportanceEnum.LOW]:    { label: '低', type: 'info' },
  [CaseImportanceEnum.MEDIUM]: { label: '中', type: 'warning' },
  [CaseImportanceEnum.HIGH]:   { label: '高', type: 'danger' },
}

export function importanceLabel(importance: number): string {
  return IMPORTANCE_MAP[importance]?.label ?? `未知(${importance})`
}

export function importanceType(importance: number): string {
  return IMPORTANCE_MAP[importance]?.type ?? 'info'
}

// ── 脚本来源 ──
export const SCRIPT_SOURCE_LABELS: Record<number, string> = {
  [ScriptSourceEnum.AI]: 'AI 生成',
  [ScriptSourceEnum.MANUAL]: '人工编写',
}

// ── 脚本状态 ──
export const SCRIPT_STATUS_LABELS: Record<number, string> = {
  [ScriptStatusEnum.DRAFT]: '草稿',
  [ScriptStatusEnum.PUBLISHED]: '已入库',
}

// ── 样本类型 ──
export const SAMPLE_TYPE_LABELS: Record<string, string> = {
  [SampleTypeEnum.CASE]: '用例样本',
  [SampleTypeEnum.SCRIPT]: '脚本样本',
}

// ── 规范类型 ──
export const SPEC_TYPE_LABELS: Record<string, string> = {
  [SpecTypeEnum.GENERAL]: '通用规范',
  [SpecTypeEnum.MODULE_SPECIFIC]: '模块专用',
  [SpecTypeEnum.COMMON_ISSUES]: '常见问题',
}

export function specTypeTag(type: string): string {
  if (type === SpecTypeEnum.GENERAL) return ''
  if (type === SpecTypeEnum.MODULE_SPECIFIC) return 'warning'
  if (type === SpecTypeEnum.COMMON_ISSUES) return 'info'
  return ''
}

// ── 核心来源 ──
export const CORE_SOURCE_LABELS: Record<number, string> = {
  [CoreSourceEnum.AI]: 'AI挑选',
  [CoreSourceEnum.MANUAL]: '人工标记',
}

export function coreSourceLabel(source: number | undefined | null): string {
  return source != null ? (CORE_SOURCE_LABELS[source] ?? '—') : '—'
}

// ── 子任务状态 ──
export const ITEM_STATUS_MAP: Record<number, { label: string; tag: string }> = {
  [ItemStatusEnum.PENDING]: { label: '排队中', tag: 'info' },
  [ItemStatusEnum.SUCCESS]: { label: '成功', tag: 'success' },
  [ItemStatusEnum.FAILED]: { label: '失败', tag: 'danger' },
}

export function itemStatusLabel(status: number): string {
  return ITEM_STATUS_MAP[status]?.label ?? `未知(${status})`
}

export function itemStatusTag(status: number): string {
  return ITEM_STATUS_MAP[status]?.tag ?? 'info'
}

// ── 脚本来源标签/颜色 ──
export function scriptSourceTag(source: number): string {
  return source === ScriptSourceEnum.AI ? 'primary' : ''
}

export function scriptSourceLabel(source: number): string {
  return SCRIPT_SOURCE_LABELS[source] ?? '未知'
}

// ── 脚本状态标签/颜色 ──
export function scriptStatusTag(status: number): string {
  return status === ScriptStatusEnum.PUBLISHED ? 'success' : 'info'
}

export function scriptStatusLabel(status: number): string {
  return SCRIPT_STATUS_LABELS[status] ?? '未知'
}

// ── 样本类型标签/颜色 ──
export function sampleTypeTag(type: string): string {
  return type === SampleTypeEnum.CASE ? 'success' : 'warning'
}

export function sampleTypeLabel(type: string): string {
  return SAMPLE_TYPE_LABELS[type] ?? type
}

// ── 审核分数颜色 ──
export function scoreTag(s: number): string {
  return s >= 80 ? 'success' : s >= 60 ? 'warning' : 'danger'
}
