/** AI 对话 — Chat API 封装 */

import request from "@/utils/request"
import { AuthStorage } from "@/utils/auth"
import type {
  ChatSession,
  SessionCreateForm,
  SessionUpdateForm,
  ChatMessage,
  MessageSendReq,
  ChatDraft,
  DraftConfirmReq,
  ContextSetReq,
  SkillInfo,
  ConfirmCreateTaskReq,
  CancelConfirmReq,
  UpdateCardStatusReq,
} from "./types"

// ═══════════════ 会话 ═══════════════

export const ChatSessionAPI = {
  /** 创建会话 */
  create(data: SessionCreateForm) {
    return request<unknown, ChatSession>({
      url: "/api/v1/aitc/chat/sessions",
      method: "post",
      data,
    })
  },

  /** 会话列表 */
  list(domain?: string) {
    return request<unknown, ChatSession[]>({
      url: "/api/v1/aitc/chat/sessions",
      method: "get",
      params: { domain },
    })
  },

  /** 会话详情 */
  get(sessionId: number) {
    return request<unknown, ChatSession>({
      url: `/api/v1/aitc/chat/sessions/${sessionId}`,
      method: "get",
    })
  },

  /** 更新会话 */
  update(sessionId: number, data: SessionUpdateForm) {
    return request<unknown, ChatSession>({
      url: `/api/v1/aitc/chat/sessions/${sessionId}`,
      method: "put",
      data,
    })
  },

  /** 删除会话 */
  delete(sessionId: number) {
    return request({
      url: `/api/v1/aitc/chat/sessions/${sessionId}`,
      method: "delete",
    })
  },
}

// ═══════════════ 消息 ═══════════════

export const ChatMessageAPI = {
  /** 消息列表 */
  list(sessionId: number) {
    return request<unknown, ChatMessage[]>({
      url: `/api/v1/aitc/chat/sessions/${sessionId}/messages`,
      method: "get",
    })
  },

  /** 发送消息 — 返回 SSE Stream */
  send(sessionId: number, data: MessageSendReq, signal?: AbortSignal): Promise<Response> {
    const baseURL = import.meta.env.VITE_APP_BASE_API || ""
    const token = AuthStorage.getAccessToken()
    return fetch(`${baseURL}/api/v1/aitc/chat/sessions/${sessionId}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
      signal,
    })
  },

  /** 取消 confirm_card 确认（多卡片并行时可指定 card_seq） */
  cancelConfirm(sessionId: number, data?: CancelConfirmReq) {
    return request({
      url: `/api/v1/aitc/chat/sessions/${sessionId}/cancel-confirm`,
      method: "post",
      data,
    })
  },

  /** 更新卡片状态（持久化 clarify/confirm 的用户操作） */
  updateCardStatus(sessionId: number, data: UpdateCardStatusReq) {
    return request({
      url: `/api/v1/aitc/chat/sessions/${sessionId}/update-card-status`,
      method: "post",
      data,
    })
  },
}

// ═══════════════ 草稿 ═══════════════

export const ChatDraftAPI = {
  /** 草稿详情 */
  get(draftId: number) {
    return request<unknown, ChatDraft>({
      url: `/api/v1/aitc/chat/drafts/${draftId}`,
      method: "get",
    })
  },

  /** 确认/丢弃草稿 */
  confirm(draftId: number, data: DraftConfirmReq) {
    return request<unknown, ChatDraft>({
      url: `/api/v1/aitc/chat/drafts/${draftId}/confirm`,
      method: "post",
      data,
    })
  },
}

// ═══════════════ 上下文 ═══════════════

export const ChatContextAPI = {
  /** 设置会话上下文 */
  set(sessionId: number, data: ContextSetReq) {
    return request({
      url: `/api/v1/aitc/chat/context`,
      method: "post",
      params: { session_id: sessionId },
      data,
    })
  },
}

// ═══════════════ 技能 ═══════════════

export const ChatSkillAPI = {
  /** 获取可用技能列表 */
  list(domain?: string) {
    return request<unknown, SkillInfo[]>({
      url: "/api/v1/aitc/chat/skills",
      method: "get",
      params: { domain },
    })
  },
}

// ═══════════════ 任务确认 ═══════════════

export interface ConfirmCreateTaskRes {
  task_ids: number[]
  total_count: number
  failed?: Array<{ suite_id: number; error: string }> | null
}

export const ChatTaskAPI = {
  /** 确认创建任务 */
  confirmCreate(sessionId: number, data: ConfirmCreateTaskReq) {
    return request<unknown, ConfirmCreateTaskRes>({
      url: `/api/v1/aitc/chat/sessions/${sessionId}/confirm-create-task`,
      method: "post",
      data,
    })
  },
}
