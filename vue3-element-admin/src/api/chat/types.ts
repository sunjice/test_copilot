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
  suite_id: number
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

// ═══════════════ Segment 区块模型（一轮回复 = 有序区块数组） ═══════════════

/** 工具区块 */
export interface ToolSegment {
  type: "tool"
  name: string
  status: "running" | "done" | "failed"
  argsSummary?: string
  startedAt: number
  durationMs?: number
  error?: string
}

/** 文本区块 */
export interface TextSegment {
  type: "text"
  content: string
}

/** 思考区块（可折叠） */
export interface ThinkingSegment {
  type: "thinking"
  content: string
  startedAt?: number   // 思考开始时间戳（performance.now()），用于显示耗时
  durationMs?: number   // 思考耗时（历史消息从 segments 中恢复）
}

export type Segment = ToolSegment | TextSegment | ThinkingSegment

// ═══════════════ SSE 事件 ═══════════════

export interface SseEvent {
  event: string
  data: Record<string, any>
}
