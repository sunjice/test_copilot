/** Chat 聊天核心逻辑 composable */

import { ref, reactive, computed, nextTick, onUnmounted } from "vue"
import { ElMessage } from "element-plus"
import { ChatSessionAPI, ChatMessageAPI, ChatDraftAPI, ChatSkillAPI, ChatContextAPI, ChatTaskAPI } from "@/api/chat/index"
import TaskAPI from "@/api/aitc/task"

import type {
  ChatSession,
  ChatMessage,
  ChatDraft,
  SkillInfo,
  MessageSendReq,
  Part,
} from "@/api/chat/types"

/** 辅助：获取最后一个 part */
function lastPart(parts: Part[]): Part | undefined {
  return parts.length > 0 ? parts[parts.length - 1] : undefined
}

/** 追加文本到末尾 text 区块（若末尾非 text 则新建） */
function appendText(parts: Part[], content: string) {
  const last = lastPart(parts)
  if (last && last.type === "text") {
    last.content += content
  } else {
    parts.push({ type: "text", content })
  }
}

/** 追加思考内容到末尾 thinking 区块（若末尾非 thinking 则新建） */
function appendThinking(parts: Part[], content: string) {
  const last = lastPart(parts)
  if (last && last.type === "thinking") {
    last.content += content
  } else {
    parts.push({ type: "thinking", content })
  }
}

export function useChat() {
  // ── 状态 ──
  const sessions = ref<ChatSession[]>([])
  const activeSessionId = ref<number | null>(null)
  const messages = ref<ChatMessage[]>([])
  const skills = ref<SkillInfo[]>([])
  const loading = ref(false)
  const streaming = ref(false)
  /** 当前流式回合的 Part 区块数组（工具/文本/思考/卡片按时间线交错） */
  const segments = ref<Part[]>([])
  const activeDraft = ref<ChatDraft | null>(null)
  const showDraftPanel = ref(false)
  const loadingSessions = ref(false)
  const loadingMessages = ref(false)
  const pageContext = ref<Record<string, any>>({})  // 页面上下文（projectId/suiteId 等）
  let abortController: AbortController | null = null  // 用于中断流式请求

  // ── 计算属性 ──
  const activeSession = computed(() =>
    sessions.value.find((s) => s.id === activeSessionId.value) || null
  )

  const pinnedSessions = computed(() =>
    sessions.value.filter((s) => s.is_pinned === 1)
  )

  const normalSessions = computed(() =>
    sessions.value.filter((s) => s.is_pinned !== 1)
  )

  // ── 会话 ──
  async function loadSessions() {
    loadingSessions.value = true
    try {
      sessions.value = await ChatSessionAPI.list()
    } catch {
      // 静默处理
    } finally {
      loadingSessions.value = false
    }
  }

  async function createSession(title?: string, contextJson?: Record<string, any>) {
    const session = await ChatSessionAPI.create({
      title: title || "新对话",
      domain: "case",
      context_json: contextJson,
    })
    sessions.value.unshift(session)
    return session
  }

  async function selectSession(sessionId: number) {
    activeSessionId.value = sessionId
    await loadMessages(sessionId)
  }

  async function updateSession(sessionId: number, data: { title?: string; is_pinned?: number }) {
    await ChatSessionAPI.update(sessionId, data)
    await loadSessions()
  }

  async function deleteSession(sessionId: number) {
    await ChatSessionAPI.delete(sessionId)
    sessions.value = sessions.value.filter((s) => s.id !== sessionId)
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = null
      messages.value = []
    }
  }

  // ── 消息 ──
  async function loadMessages(sessionId: number) {
    loadingMessages.value = true
    try {
      messages.value = await ChatMessageAPI.list(sessionId)

      // 为未完成的 task_card 启动状态监控
      await nextTick()
      await monitorIncompleteTasks()
    } catch {
      messages.value = []
    } finally {
      loadingMessages.value = false
    }
  }

  function addLocalMessage(msg: ChatMessage) {
    messages.value.push(msg)
  }

  /** 停止当前生成 */
  function stopGeneration() {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    streaming.value = false
    segments.value = []
  }

  /** 重试最后一条消息（发送最后一条用户消息） */
  async function retryLastMessage() {
    // 找到最后一条用户消息
    let lastUserContent = ""
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].role === "user") {
        lastUserContent = messages.value[i].content || ""
        break
      }
    }
    if (!lastUserContent) return

    // 移除最后的 assistant 和 error 消息
    while (
      messages.value.length > 0 &&
      messages.value[messages.value.length - 1].role !== "user"
    ) {
      messages.value.pop()
    }

    await sendMessage(lastUserContent)
  }

  async function sendMessage(content: string, skillName?: string): Promise<void> {
    // 解析 slash 命令：/case_review xxx → skill_name = case_review
    let skill = skillName
    if (!skill) {
      const m = content.match(/^\/([a-zA-Z_][a-zA-Z0-9_]*)/)
      if (m) skill = m[1]
    }

    if (!activeSessionId.value) {
      // 自动创建会话，带上页面上下文
      const session = await createSession(undefined, { ...pageContext.value })
      activeSessionId.value = session.id!
    }

    // 同步当前页面上下文到后端会话（用户可能切换了项目/模块）
    const ctx = pageContext.value
    if (ctx && Object.keys(ctx).length > 0 && activeSessionId.value) {
      await ChatContextAPI.set(activeSessionId.value, { context_json: ctx }).catch(() => {})
    }

    const sessionId = activeSessionId.value!

    // 添加用户消息到本地
    const userMsg: ChatMessage = {
      id: null,
      session_id: sessionId,
      role: "user",
      msg_type: "text",
      content,
      metadata_json: null,
      draft_id: null,
      create_time: new Date().toISOString(),
    }
    addLocalMessage(userMsg)

    streaming.value = true
    segments.value = []

    // 创建新的 AbortController
    abortController = new AbortController()

    try {
      const req: MessageSendReq = skill ? { content, skill_name: skill } : { content }
      const response = await ChatMessageAPI.send(sessionId, req, abortController.signal)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error("No response body")

      const decoder = new TextDecoder()
      let buffer = ""
      let assistantContent = ""
      let assistantMsgType = "text" as ChatMessage["msg_type"]
      let draftType: string | undefined
      let draftData: Record<string, any> | undefined
      let skillName: string | undefined
      const draftId: number | null = null
      // 单一事实来源：后端只产出一条 message 事件（parts 内嵌卡片），这里收集单条
      let collectedMessage: {
        content: string
        msg_type: ChatMessage["msg_type"]
        draft_type?: string
        draft_data?: Record<string, any>
        skill_name?: string
        metadata: Record<string, any>
      } | null = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        let eventType = ""
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6).trim())

              switch (eventType) {
                case "thinking":
                  // 思考内容流式推送：追加到末尾 thinking 区块（若末尾非 thinking 则新建）
                  if (data.content) {
                    appendThinking(segments.value, data.content)
                  } else if (segments.value.length === 0 || !lastPart(segments.value)?.type.includes("thinking")) {
                    // Agent 初始心跳：创建思考区块
                    segments.value.push({ type: "thinking", content: "" })
                  }
                  break

                case "chunk":
                  appendText(segments.value, data.content || "")
                  break

                case "skill_start":
                  skillName = data.skill_name
                  break

                case "tool_start":
                  // 工具开始执行 → 新建 running 工具区块（id 用 run_id 精确关联）
                  segments.value.push({
                    type: "tool",
                    id: data.run_id || data.id || `tool-${Date.now()}`,
                    name: data.name || "处理中",
                    status: "running",
                  })
                  break

                case "tool_end":
                  // 工具执行完成 → 按 run_id 精确结算（多任务并行不串台）
                  {
                    const runId = data.run_id || data.id || ""
                    let settled = false
                    for (let i = segments.value.length - 1; i >= 0; i--) {
                      const seg = segments.value[i]
                      if (seg.type === "tool" && seg.status === "running") {
                        if (runId && seg.id === runId) {
                          seg.status = data.error ? "failed" : "done"
                          seg.durationMs = data.durationMs ?? 0
                          if (data.error) seg.error = data.error
                          settled = true
                          break
                        }
                      }
                    }
                    if (!settled) {
                      // 兜底：run_id 缺失时结算最后一个 running 工具
                      for (let i = segments.value.length - 1; i >= 0; i--) {
                        const seg = segments.value[i]
                        if (seg.type === "tool" && seg.status === "running") {
                          seg.status = data.error ? "failed" : "done"
                          seg.durationMs = data.durationMs ?? 0
                          if (data.error) seg.error = data.error
                          break
                        }
                      }
                    }
                  }
                  break

                case "message":
                  assistantContent = data.content || ""
                  assistantMsgType = data.msg_type || "text"
                  if (data.draft_type) draftType = data.draft_type
                  if (data.draft_data) draftData = data.draft_data
                  if (data.skill_name) skillName = data.skill_name
                  // 单一事实来源：单条 message，parts 内嵌卡片
                  collectedMessage = {
                    content: data.content || "",
                    msg_type: (data.msg_type || "text") as ChatMessage["msg_type"],
                    draft_type: data.draft_type,
                    draft_data: data.draft_data,
                    skill_name: data.skill_name || skillName,
                    metadata: data.metadata || {},
                  }
                  break

                case "error":
                  // 不再只弹 toast，后续会作为错误消息插入列表
                  throw new Error(data.message || "服务端处理出错")
              }
            } catch (parseErr: any) {
              // 如果是主动抛出的错误，继续向上传播
              if (parseErr.message && !parseErr.message.includes("JSON")) {
                throw parseErr
              }
              // JSON 解析失败，跳过
            }
          }
        }
      }

      // SSE 流已结束，先关闭 streaming 占位符，再 push 真消息
      streaming.value = false

      // 添加助手消息：后端单一事实来源（单条 message，parts 内嵌卡片）
      if (collectedMessage) {
        const cm = collectedMessage
        const meta: Record<string, any> = { ...(cm.metadata || {}) }
        // 后端 message 已带 parts（单一事实来源），直接用
        if (!meta.parts && segments.value.length) {
          meta.parts = JSON.parse(JSON.stringify(segments.value))
        }
        if (!meta.skill_name && (cm.skill_name || skillName)) {
          meta.skill_name = cm.skill_name || skillName
        }

        const assistantMsg: ChatMessage = {
          id: null,
          session_id: sessionId,
          role: "assistant",
          msg_type: cm.msg_type,
          content: cm.content,
          metadata_json: Object.keys(meta).length > 0
            ? meta
            : (cm.skill_name || skillName)
              ? { skill_name: cm.skill_name || skillName }
              : null,
          draft_id: draftId,
          create_time: new Date().toISOString(),
        }
        addLocalMessage(assistantMsg)

        // 如果有草稿数据，打开草稿面板
        if (cm.draft_type && cm.draft_data) {
          activeDraft.value = {
            id: null,
            session_id: sessionId,
            message_id: null,
            draft_type: cm.draft_type,
            title: cm.draft_type,
            content_json: cm.draft_data,
            status: "pending",
            confirmed_by: null,
            confirmed_at: null,
            create_time: null,
          }
          showDraftPanel.value = true
        }
      } else if (assistantContent || segments.value.some(s => s.type === "text" && s.content)) {
        // 无 message 事件（兜底）：从 parts 中提取纯文本拼接
        const textFromParts = segments.value
          .filter((s): s is Part & { type: "text" } => s.type === "text")
          .map((s) => s.content)
          .join("")

        const assistantMsg: ChatMessage = {
          id: null,
          session_id: sessionId,
          role: "assistant",
          msg_type: assistantMsgType,
          content: assistantContent || textFromParts,
          metadata_json: segments.value.length
            ? { parts: JSON.parse(JSON.stringify(segments.value)) }
            : skillName
              ? { skill_name: skillName }
              : null,
          draft_id: draftId,
          create_time: new Date().toISOString(),
        }
        addLocalMessage(assistantMsg)

        // 如果有草稿数据，打开草稿面板
        if (draftType && draftData) {
          activeDraft.value = {
            id: null,
            session_id: sessionId,
            message_id: null,
            draft_type: draftType,
            title: draftType,
            content_json: draftData,
            status: "pending",
            confirmed_by: null,
            confirmed_at: null,
            create_time: null,
          }
          showDraftPanel.value = true
        }
      }

      segments.value = []

      // 刷新会话列表（更新消息计数和时间）
      await loadSessions()
    } catch (e: any) {
      // 如果是用户主动中断，不显示错误
      if (e.name === "AbortError") {
        // 保留已输出的部分内容作为消息
        if (segments.value.length) {
          const textFromParts = segments.value
            .filter((s): s is Part & { type: "text" } => s.type === "text")
            .map((s) => s.content)
            .join("")

          if (textFromParts) {
            const parts = JSON.parse(JSON.stringify(segments.value))
            const md: Record<string, any> = {
              parts,
            }
            const toolNames = parts
              .filter((s: Part) => s.type === "tool")
              .map((s: any) => s.name)
            if (toolNames.length) {
              md.tool_names = toolNames
              md.tool_calls = toolNames.length
            }
            const partialMsg: ChatMessage = {
              id: null,
              session_id: sessionId,
              role: "assistant",
              msg_type: "text",
              content: textFromParts + "\n\n*[已停止生成]*",
              metadata_json: Object.keys(md).length > 0 ? md : null,
              draft_id: null,
              create_time: new Date().toISOString(),
            }
            addLocalMessage(partialMsg)
          }
        }
      } else {
        // 推送错误消息到列表
        const errMsg: ChatMessage = {
          id: null,
          session_id: sessionId,
          role: "system",
          msg_type: "error",
          content: e.message || "请求失败，请重试",
          metadata_json: {
            error: true,
            last_user_message: content,
          } as any,
          draft_id: null,
          create_time: new Date().toISOString(),
        }
        addLocalMessage(errMsg)
      }
    } finally {
      streaming.value = false
      segments.value = []
      abortController = null
    }
  }

  // ── 草稿 ──
  async function confirmDraft(action: "confirm" | "discard", editedContent?: Record<string, any>) {
    if (!activeDraft.value?.id) return
    try {
      await ChatDraftAPI.confirm(activeDraft.value.id, {
        action,
        edited_content: editedContent,
      })
      // 回写本地 draft_card 消息的 metadata_json
      const draftId = activeDraft.value.id
      for (let i = messages.value.length - 1; i >= 0; i--) {
        const m = messages.value[i]
        if (m.msg_type === "draft_card" && m.draft_id === draftId) {
          messages.value[i] = {
            ...m,
            metadata_json: { ...(m.metadata_json || {}), draft_status: action },
          }
          break
        }
      }
      if (action === "confirm") {
        ElMessage.success("草稿已确认")
      } else {
        ElMessage.info("草稿已丢弃")
      }
      showDraftPanel.value = false
      activeDraft.value = null
    } catch (e: any) {
      ElMessage.error(`操作失败: ${e.message}`)
    }
  }

  async function viewDraft(draftId: number) {
    try {
      activeDraft.value = await ChatDraftAPI.get(draftId)
      showDraftPanel.value = true
    } catch {
      ElMessage.error("加载草稿失败")
    }
  }

  function closeDraftPanel() {
    showDraftPanel.value = false
    activeDraft.value = null
  }

  // ── 任务确认 ──

  /** 活跃的任务状态轮询器: task_id → intervalId */
  const taskMonitors = new Map<number, ReturnType<typeof setInterval>>()

  onUnmounted(() => {
    taskMonitors.forEach((id) => clearInterval(id))
    taskMonitors.clear()
  })

  /** 更新任务状态：定位 parts 里的 confirm_card part（按 task_id 或 task_ids 匹配）。
   *  多任务卡片（task_ids 数组）时聚合各任务进度到同一张卡片。 */
  function updateConfirmCardTaskStatus(taskId: number, status: number, done: number, total: number) {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const m = messages.value[i]
      const parts = m.metadata_json?.parts
      if (!Array.isArray(parts)) continue
      let changed = false
      const newParts = parts.map((p: any) => {
        if (p?.type !== "confirm_card") return p
        const card = p.card || {}
        const ids: number[] = card.task_ids || (card.task_id != null ? [card.task_id] : [])
        if (!ids.includes(Number(taskId))) return p
        changed = true

        // 多任务：维护每个任务的进度快照并聚合；单任务：直接使用本次进度
        if (ids.length > 1) {
          const progress = { ...(card._task_progress || {}) }
          progress[taskId] = { status, done, total }
          const vals = Object.values(progress) as Array<{ status: number; done: number; total: number }>
          const aggDone = vals.reduce((s, v) => s + (v.done || 0), 0)
          const aggTotal = vals.reduce((s, v) => s + (v.total || 0), 0)
          const allDone = vals.length === ids.length && vals.every((v) => v.status >= 2)
          const anyFailed = vals.some((v) => v.status === 3)
          const aggStatus = allDone ? (anyFailed ? 3 : 2) : (vals.some((v) => v.status >= 1) ? 1 : 0)
          return {
            ...p,
            card: { ...card, _task_progress: progress, task_status: aggStatus, done_count: aggDone, total_count: aggTotal },
          }
        }

        return { ...p, card: { ...card, task_status: status, done_count: done, total_count: total } }
      })
      if (changed) {
        messages.value[i] = {
          ...m,
          metadata_json: { ...(m.metadata_json || {}), parts: newParts },
        }
        return
      }
    }
  }

  function startTaskMonitor(taskId: number, skillName: string) {
    if (taskMonitors.has(taskId)) return

    const intervalId = setInterval(async () => {
      try {
        const detail = await TaskAPI.getDetail(String(taskId))
        const task = detail.task

        // 更新确认卡片 part 中的任务状态
        updateConfirmCardTaskStatus(taskId, task.status, task.done_count ?? 0, task.total_count ?? 0)

        if (task.status >= 2) {
          // COMPLETED(2) 或 FAILED(3) — 停止轮询
          clearInterval(intervalId)
          taskMonitors.delete(taskId)
        }
      } catch {
        // 静默处理轮询错误
      }
    }, 2000)

    taskMonitors.set(taskId, intervalId)
  }

  /** 为已加载的历史消息中未完成任务启动监控，同时补齐已完成/失败任务的计数。
   * 卡片已内嵌在消息的 parts 里，这里遍历 parts 找 confirm_card part 的 task_id。 */
  async function monitorIncompleteTasks() {
    for (let i = 0; i < messages.value.length; i++) {
      const msg = messages.value[i]
      const parts = msg.metadata_json?.parts
      if (!Array.isArray(parts)) continue

      for (let pi = 0; pi < parts.length; pi++) {
        const p = parts[pi] as any
        if (p?.type !== "confirm_card") continue
        const taskIds: number[] = p.card?.task_ids || (p.card?.task_id != null ? [p.card.task_id] : [])
        if (!taskIds.length) continue
        const ts = p.card?.task_status

        // 逐个任务补齐/监控
        for (const taskId of taskIds) {
          // 已完成/失败但缺少计数，从服务端补齐
          if (ts != null && ts >= 2) {
            if ((p.card?.done_count ?? 0) === 0 && (p.card?.total_count ?? 0) === 0) {
              try {
                const detail = await TaskAPI.getDetail(String(taskId))
                const task = detail.task
                updateConfirmCardTaskStatus(taskId, task.status, task.done_count ?? 0, task.total_count ?? 0)
              } catch { /* 静默 */ }
            }
            continue
          }

          // 未完成任务，启动监控
          if (taskMonitors.has(taskId)) continue
          try {
            const detail = await TaskAPI.getDetail(String(taskId))
            const task = detail.task
            updateConfirmCardTaskStatus(taskId, task.status, task.done_count ?? 0, task.total_count ?? 0)
            if (task.status >= 2) continue
            const skillName = p.card?.skill_name || p.card?.task_type || ""
            startTaskMonitor(taskId, skillName)
          } catch {
            // 静默处理
          }
        }
      }
    }
  }

  async function confirmCreateTask(metadata: Record<string, any>) {
    if (!activeSessionId.value) return

    const sessionId = activeSessionId.value
    const skillName = metadata.skill_name || ""
    const projectId = metadata.project_id
    const suiteIds: number[] = metadata.suite_ids ?? (metadata.suite_id != null ? [metadata.suite_id] : [])
    const caseIds: number[] | undefined = metadata.case_ids ?? undefined
    const selectedOption = metadata.selected_option as string | undefined
    const cardSeq = (metadata.card_seq as number | null | undefined) ?? null

    try {
      const res = await ChatTaskAPI.confirmCreate(sessionId, {
        skill_name: skillName,
        project_id: projectId,
        suite_ids: suiteIds,
        case_ids: caseIds ?? null,
        selected_option: selectedOption ?? null,
        card_seq: cardSeq,
      })

      const taskIds: number[] = res.task_ids ?? (res.task_id != null ? [res.task_id] : [])
      const total = res.total_count ?? metadata.total ?? 0

      // 回写本地卡片 part：标记已确认 + 写入任务字段
      updateCardStatusInMessages(cardSeq, "confirmed", selectedOption, {
        task_ids: taskIds,
        total_count: total,
        failed: res.failed ?? null,
      })

      await loadSessions()

      // 逐个启动任务状态轮询
      taskIds.forEach((taskId) => {
        if (taskId) startTaskMonitor(taskId, skillName)
      })

      const failedCount = res.failed?.length ?? 0
      if (failedCount) {
        ElMessage.warning(`已创建 ${taskIds.length} 个任务，${failedCount} 个模块创建失败`)
      } else {
        ElMessage.success(`已创建 ${taskIds.length} 个任务`)
      }
    } catch (e: any) {
      ElMessage.error(`创建任务失败: ${e.message || e}`)
      throw e
    }
  }

  async function cancelTask(_metadata: Record<string, any>) {
    if (!activeSessionId.value) return
    const cardSeq = (_metadata.card_seq as number | null | undefined) ?? null
    try {
      await ChatMessageAPI.cancelConfirm(activeSessionId.value, { card_seq: cardSeq })
      updateCardStatusInMessages(cardSeq, "cancelled")
    } catch {
      // 静默处理
    }
    ElMessage.info("已取消创建")
  }

  /** 在消息的 parts 里定位 confirm_card part（card_seq 匹配，空则回退最后一张未处理的），更新其 card 字段 */
  function updateCardStatusInMessages(
    cardSeq: number | null,
    status: string,
    selectedOption?: string,
    taskFields?: Record<string, any>,
  ) {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const m = messages.value[i]
      const parts = m.metadata_json?.parts
      if (!Array.isArray(parts)) continue
      // 定位目标 part
      let targetIdx = -1
      if (cardSeq != null) {
        for (let pi = 0; pi < parts.length; pi++) {
          const p = parts[pi] as any
          if (p?.type === "confirm_card" && p.card?.card_seq === cardSeq) {
            targetIdx = pi
            break
          }
        }
      } else {
        for (let pi = parts.length - 1; pi >= 0; pi--) {
          const p = parts[pi] as any
          if (p?.type === "confirm_card" && p.card?.state !== "confirmed" && p.card?.state !== "cancelled") {
            targetIdx = pi
            break
          }
        }
      }
      if (targetIdx === -1) continue
      const newParts = parts.map((p: any, pi: number) => {
        if (pi !== targetIdx) return p
        const card = { ...(p.card || {}), state: status }
        if (selectedOption) card.selected_option = selectedOption
        if (taskFields) Object.assign(card, taskFields)
        return { ...p, card }
      })
      messages.value[i] = {
        ...m,
        metadata_json: { ...(m.metadata_json || {}), parts: newParts },
      }
      return
    }
  }

  /** 将最后一条 clarify_card 标记为已提交，并将答案持久化 */
  async function submitClarifyAnswers(answers: Record<string, string>) {
    // 本地更新
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const m = messages.value[i]
      if (m.msg_type === "clarify_card" && !m.metadata_json?.clarify_status) {
        messages.value[i] = {
          ...m,
          metadata_json: {
            ...(m.metadata_json || {}),
            clarify_status: "submitted",
            clarify_answers: answers,
          },
        }
        break
      }
    }
    // 持久化到后端
    if (activeSessionId.value) {
      ChatMessageAPI.updateCardStatus(activeSessionId.value, {
        msg_type: "clarify_card",
        metadata: { clarify_status: "submitted", clarify_answers: answers },
      }).catch(() => {})
    }
  }

  /** 将最后一条 clarify_card 标记为已取消并持久化 */
  async function cancelClarify() {
    // 本地更新
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const m = messages.value[i]
      if (m.msg_type === "clarify_card" && !m.metadata_json?.clarify_status) {
        messages.value[i] = {
          ...m,
          metadata_json: {
            ...(m.metadata_json || {}),
            clarify_status: "cancelled",
          },
        }
        break
      }
    }
    // 持久化到后端
    if (activeSessionId.value) {
      ChatMessageAPI.updateCardStatus(activeSessionId.value, {
        msg_type: "clarify_card",
        metadata: { clarify_status: "cancelled" },
      }).catch(() => {})
    }
  }

  // ── 技能 ──
  async function loadSkills() {
    try {
      skills.value = await ChatSkillAPI.list()
    } catch {
      skills.value = []
    }
  }

  // ── 初始化 ──
  async function init() {
    await Promise.all([loadSessions(), loadSkills()])
  }

  return {
    // 状态
    sessions,
    activeSessionId,
    activeSession,
    pinnedSessions,
    normalSessions,
    messages,
    skills,
    loading,
    loadingSessions,
    loadingMessages,
    streaming,
    segments,
    activeDraft,
    showDraftPanel,
    pageContext,

    // 方法
    loadSessions,
    createSession,
    selectSession,
    updateSession,
    deleteSession,
    loadMessages,
    sendMessage,
    stopGeneration,
    retryLastMessage,
    confirmDraft,
    viewDraft,
    closeDraftPanel,
    confirmCreateTask,
    cancelTask,
    submitClarifyAnswers,
    cancelClarify,
    loadSkills,
    monitorIncompleteTasks,
    init,
  }
}
