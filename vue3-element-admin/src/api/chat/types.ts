/** AI 对话 — Chat 模块类型定义 */

// ═══════════════ 会话 ═══════════════

export interface ChatSession {
  id: number | null
  title: string
  domain: string
  context_json: Record<string, any> | null
  message_count: number
  is_pinned: number
  user_id: number | null
  create_time: string | null
  update_time: string | null
}

export interface SessionCreateForm {
  title?: string
  domain?: string
  context_json?: Record<string, any>
}

export interface SessionUpdateForm {
  title?: string
  is_pinned?: number
}

// ═══════════════ 消息 ═══════════════

export interface ChatMessage {
  id: number | null
  session_id: number | null
  role: 'user' | 'assistant' | 'system'
  msg_type: 'text' | 'action_card' | 'task_card' | 'draft_card' | 'clarify_card' | 'help_card' | 'confirm_card' | 'error'
  content: string
  metadata_json: Record<string, any> | null
  draft_id: number | null
  create_time: string | null
}

export interface MessageSendReq {
  content: string
  skill_name?: string
}

// ═══════════════ 草稿 ═══════════════

export interface ChatDraft {
  id: number | null
  session_id: number | null
  message_id: number | null
  draft_type: string
  title: string
  content_json: Record<string, any> | null
  status: 'pending' | 'confirmed' | 'applied' | 'discarded'
  confirmed_by: string | null
  confirmed_at: string | null
  create_time: string | null
}

export interface DraftConfirmReq {
  action: 'confirm' | 'discard'
  edited_content?: Record<string, any>
}

// ═══════════════ 上下文 ═══════════════

export interface ContextSetReq {
  domain?: string
  context_json: Record<string, any>
}

// ═══════════════ 技能 ═══════════════

export interface SkillInfo {
  name: string
  domain: string
  description: string
  mode: 'SYNC' | 'ASYNC'
  keywords: string[]
}

// ═══════════════ 任务确认 ═══════════════

export interface ConfirmCreateTaskReq {
  skill_name: string
  project_id: number
  suite_ids: number[]
  case_ids?: number[] | null
  selected_option?: string | null
  /** 卡片序号（多卡片并行时精确定位，缺省回退最后一张） */
  card_seq?: number | null
}

/** 取消确认卡片请求（多卡片并行时可指定序号） */
export interface CancelConfirmReq {
  card_seq?: number | null
}

/** 更新卡片状态 */
export interface UpdateCardStatusReq {
  msg_type: string
  metadata: Record<string, any>
}

// ═══════════════ Part 区块模型（一轮回复 = 有序区块数组，后端单一事实来源） ═══════════════
// 对齐 Anthropic content blocks / Vercel message parts 范式。
// 时间只保留 durationMs（时长），不暴露时间戳，避免前后端时间基准不一致。

/** 工具区块 */
export interface ToolPart {
  type: "tool"
  id: string            // 工具调用 run_id，用于并行时精确结算
  name: string
  status: "running" | "done" | "failed"
  argsSummary?: string
  durationMs?: number
  error?: string
}

/** 文本区块 */
export interface TextPart {
  type: "text"
  content: string
}

/** 思考区块（可折叠） */
export interface ThinkingPart {
  type: "thinking"
  content: string
  durationMs?: number
}

/** 确认卡片区块（任务创建确认，内嵌任务进度） */
export interface ConfirmCardPart {
  type: "confirm_card"
  card: ConfirmCardData
}

/** 澄清卡片区块 */
export interface ClarifyCardPart {
  type: "clarify_card"
  card: Record<string, any>
}

export type Part = ToolPart | TextPart | ThinkingPart | ConfirmCardPart | ClarifyCardPart

/** 确认卡片数据（状态机：idle → confirmed → running → done/failed） */
export interface ConfirmCardData {
  card_seq?: number
  content?: string
  msg_type?: string
  project_name?: string
  suite_name?: string
  suite_names?: string[]
  suite_ids?: number[]
  task_type?: string
  task_label?: string
  skill_name?: string
  total?: number
  options?: Array<{ id: string; label: string; description?: string }>
  /** 卡片状态 */
  state?: "idle" | "confirmed" | "cancelled"
  /** 任务进度（确认后由轮询更新） */
  task_id?: number | null
  task_ids?: number[]
  task_status?: number
  done_count?: number
  total_count?: number
  selected_option?: string | null
  /** 多模块创建失败摘要 */
  failed?: Array<{ suite_id: number; error: string }> | null
  /** 内部字段：多任务进度快照（taskId -> 进度），仅前端运行时使用 */
  _task_progress?: Record<number, { status: number; done: number; total: number }>
}

// 向后兼容别名（部分旧代码仍引用 Segment 名称）
export type Segment = Part
export type ToolSegment = ToolPart
export type TextSegment = TextPart
export type ThinkingSegment = ThinkingPart

// ═══════════════ SSE 事件 ═══════════════

export interface SseEvent {
  event: string
  data: Record<string, any>
}
