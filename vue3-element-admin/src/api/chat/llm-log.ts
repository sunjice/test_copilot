/** AI 运行轨迹 — API 封装 + 类型定义（对齐后端 ai_run_events 新表） */

import request from "@/utils/request"
import type { PageResult } from "@/api/common"

// ── 类型 ──

export interface AiRunEvent {
  id: number
  session_id: number | null
  message_id: number | null
  seq: number
  event_type: string
  module: string
  action: string
  tool_call_id: string | null
  provider: string
  api_base: string
  model: string
  status: string
  error_msg: string | null
  prompt_tokens: number
  prompt_cache_hit_tokens: number
  prompt_cache_miss_tokens: number
  prompt_cache_write_tokens: number
  completion_tokens: number
  reasoning_tokens: number
  duration_ms: number
  create_time: string | null
  // 详情额外字段
  request_messages?: Record<string, any> | null
  response_raw?: string | null
  response_json?: Record<string, any> | null
}

export interface LlmLogSession {
  session_id: number
  last_time: string | null
  log_count: number
}

export interface MessageUsage {
  request_count: number
  prompt_tokens: number
  prompt_cache_hit_tokens: number
  prompt_cache_miss_tokens: number
  prompt_cache_write_tokens: number
  completion_tokens: number
  reasoning_tokens: number
  reply_tokens: number
  cache_hit_rate: number
}

export interface DailyUsageItem {
  stat_date: string
  provider: string
  model: string
  api_base: string
  request_count: number
  prompt_tokens: number
  prompt_cache_hit_tokens: number
  prompt_cache_miss_tokens: number
  prompt_cache_write_tokens: number
  completion_tokens: number
  reasoning_tokens: number
  cost_cny: number
}

export interface LlmLogQuery {
  pageNum: number
  pageSize: number
  session_id?: number | null
  message_id?: number | null
  action?: string
  status?: string
  module?: string
  provider?: string
}

// ── API ──

export const LlmLogAPI = {
  /** 分页列表 */
  getPage(params: LlmLogQuery) {
    const clean: Record<string, any> = {}
    Object.entries(params).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== "") clean[k] = v
    })
    return request<unknown, PageResult<AiRunEvent>>({
      url: "/api/v1/llm-logs",
      method: "get",
      params: clean,
    })
  },

  /** 单条详情（含 request_messages / response） */
  getDetail(logId: number) {
    return request<unknown, AiRunEvent>({
      url: `/api/v1/llm-logs/${logId}`,
      method: "get",
    })
  },

  /** 有日志的会话列表 */
  getSessions() {
    return request<unknown, LlmLogSession[]>({
      url: "/api/v1/llm-logs/sessions/list",
      method: "get",
    })
  },

  /** 某一轮对话的完整调用轨迹（seq 平铺） */
  getTrace(messageId: number) {
    return request<unknown, AiRunEvent[]>({
      url: `/api/v1/llm-logs/trace/${messageId}`,
      method: "get",
    })
  },

  /** 某一轮对话的用量汇总 */
  getMessageUsage(messageId: number) {
    return request<unknown, MessageUsage>({
      url: `/api/v1/llm-logs/usage/message/${messageId}`,
      method: "get",
    })
  },

  /** 按日用量汇总 */
  getDailyUsage(params?: {
    start_date?: string
    end_date?: string
    provider?: string
    model?: string
  }) {
    const clean: Record<string, any> = {}
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== null && v !== undefined && v !== "") clean[k] = v
      })
    }
    return request<unknown, DailyUsageItem[]>({
      url: "/api/v1/llm-logs/usage/daily",
      method: "get",
      params: clean,
    })
  },

  /** 导出日志文件（返回 blob 下载） */
  async export(params: {
    format: "json" | "txt"
    session_id?: number | null
    message_id?: number | null
    action?: string
    status?: string
    module?: string
    provider?: string
  }) {
    const baseURL = import.meta.env.VITE_APP_BASE_API || ""
    const token = localStorage.getItem("accessToken") || ""
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        searchParams.set(k, String(v))
      }
    })
    const resp = await fetch(
      `${baseURL}/api/v1/llm-logs/export?${searchParams.toString()}`,
      {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      }
    )
    if (!resp.ok) throw new Error("导出失败")
    const blob = await resp.blob()
    const filename = params.format === "txt" ? "llm_trace.txt" : "llm_trace.json"
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  },
}
