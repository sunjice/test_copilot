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
  Segment,
} from "@/api/chat/types"

/** 辅助：获取最后一个 segment */
function lastSeg(segments: Segment[]): Segment | undefined {
  return segments.length > 0 ? segments[segments.length - 1] : undefined
}

/** 追加文本到末尾 text 区块（若末尾非 text 则新建） */
function appendText(segments: Segment[], content: string) {
  const last = lastSeg(segments)
  if (last && last.type === "text") {
    last.content += content
  } else {
    segments.push({ type: "text", content })
  }
}

/** 追加思考内容到末尾 thinking 区块（若末尾非 thinking 则新建） */
function appendThinking(segments: Segment[], content: string) {
  const last = lastSeg(segments)
  if (last && last.type === "thinking") {
    last.content += content
  } else {
    segments.push({ type: "thinking", content, startedAt: performance.now() })
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
  /** 当前流式回合的 Segment 区块数组（工具/文本/思考按时间线交错） */
  const segments = ref<Segment[]>([])
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
      // 收集所有 message 事件（多卡片并行时每条独立展示，避免互相覆盖）
      const collectedMessages: Array<{
        content: string
        msg_type: ChatMessage["msg_type"]
        draft_type?: string
        draft_data?: Record<string, any>
        skill_name?: string
        metadata: Record<string, any>
      }> = []

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
                  } else if (segments.value.length === 0 || (!lastSeg(segments.value)?.type.includes("thinking"))) {
                    // Agent 初始心跳：创建思考区块并记录开始时间
                    segments.value.push({ type: "thinking", content: "", startedAt: performance.now() })
                  }
                  break

                case "chunk":
                  appendText(segments.value, data.content || "")
                  break

                case "skill_start":
                  skillName = data.skill_name
                  break

                case "tool_start":
                  // 工具开始执行 → 新建 running 工具区块
                  segments.value.push({
                    type: "tool",
                    name: data.name || "处理中",
                    status: "running",
                    startedAt: performance.now(),
                  })
                  break

                case "tool_end":
                  // 工具执行完成 → 结算最后一个 running 工具区块
                  for (let i = segments.value.length - 1; i >= 0; i--) {
                    const seg = segments.value[i]
                    if (seg.type === "tool" && seg.status === "running") {
                      seg.status = data.error ? "failed" : "done"
                      seg.durationMs = Math.round(performance.now() - seg.startedAt)
                      if (data.error) seg.error = data.error
                      break
                    }
                  }
                  break

                case "message":
                  assistantContent = data.content || ""
                  assistantMsgType = data.msg_type || "text"
                  if (data.draft_type) draftType = data.draft_type
                  if (data.draft_data) draftData = data.draft_data
                  if (data.skill_name) skillName = data.skill_name
                  // 收集所有 message 事件（多卡片并行时每条独立 addLocalMessage，避免互相覆盖）
                  collectedMessages.push({
                    content: data.content || "",
                    msg_type: (data.msg_type || "text") as ChatMessage["msg_type"],
                    draft_type: data.draft_type,
                    draft_data: data.draft_data,
                    skill_name: data.skill_name || skillName,
                    metadata: data.metadata || {},
                  })
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

      // 把本地拼的 segments 序列化（后端 message 事件未携带 segments 时的兜底）
      const localSegmentMeta: Record<string, any> = {}
      if (segments.value.length) {
        // 流已结束，给未结算的思考区块补上 durationMs
        const now = performance.now()
        const finalizedSegments = segments.value.map((s) => {
          if (s.type === "thinking" && s.startedAt != null && s.durationMs == null) {
            return { ...s, durationMs: Math.round(now - s.startedAt) }
          }
          return s
        })

        // 合并连续的 text 区块为一个（避免 tool 打断 text 导致 TurnRenderer 渲染多段）
        const merged: Segment[] = []
        for (const seg of finalizedSegments) {
          const last = merged.length > 0 ? merged[merged.length - 1] : null
          if (seg.type === "text" && last && last.type === "text") {
            last.content += seg.content
          } else {
            merged.push({ ...seg })
          }
        }

        // 提取工具区块名称列表
        const toolNames = merged
          .filter((s): s is Segment & { type: "tool" } => s.type === "tool")
          .map((s) => s.name)

        localSegmentMeta.segments = JSON.parse(JSON.stringify(merged))
        localSegmentMeta.tool_names = toolNames
        localSegmentMeta.tool_calls = toolNames.length
      }

      // 添加助手消息：多卡片并行时逐条添加，互不覆盖
      if (collectedMessages.length > 0) {
        for (const cm of collectedMessages) {
          const meta: Record<string, any> = { ...(cm.metadata || {}) }
          // 后端 message 事件已带 segments（agent 路径）→ 优先使用；否则用本地拼的兜底
          if (!meta.segments && Object.keys(localSegmentMeta).length > 0) {
            Object.assign(meta, localSegmentMeta)
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

          // 如果有草稿数据，打开草稿面板（多草稿时取最后一个）
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
        }
      } else if (assistantContent || segments.value.some(s => s.type === "text" && s.content)) {
        // 无 message 事件（兜底）：从 segments 中提取纯文本拼接
        const textFromSegments = segments.value
          .filter((s): s is Segment & { type: "text" } => s.type === "text")
          .map((s) => s.content)
          .join("")

        const assistantMsg: ChatMessage = {
          id: null,
          session_id: sessionId,
          role: "assistant",
          msg_type: assistantMsgType,
          content: assistantContent || textFromSegments,
          metadata_json: Object.keys(localSegmentMeta).length > 0
            ? localSegmentMeta
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
          const textFromSegments = segments.value
            .filter((s): s is Segment & { type: "text" } => s.type === "text")
            .map((s) => s.content)
            .join("")

          if (textFromSegments) {
            const now = performance.now()
            const finalizedSegments = segments.value.map((s) => {
              if (s.type === "thinking" && s.startedAt != null && s.durationMs == null) {
                return { ...s, durationMs: Math.round(now - s.startedAt) }
              }
              return s
            })
            const md: Record<string, any> = {
              segments: JSON.parse(JSON.stringify(finalizedSegments)),
            }
            const toolNames = finalizedSegments
              .filter((s): s is Segment & { type: "tool" } => s.type === "tool")
              .map((s) => s.name)
            if (toolNames.length) {
              md.tool_names = toolNames
              md.tool_calls = toolNames.length
            }
            const partialMsg: ChatMessage = {
              id: null,
              session_id: sessionId,
              role: "assistant",
              msg_type: "text",
              content: textFromSegments + "\n\n*[已停止生成]*",
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

  /** 创建/查找进度消息并轮询任务状态，完成后更新消息内容 */
  /** 更新任务状态：同时更新 confirm_card（新逻辑）与 task_card（兼容历史数据） */
  function updateConfirmCardTaskStatus(taskId: number, status: number, done: number, total: number) {
    // 1) 优先更新 confirm_card（新逻辑：任务进度内嵌在确认卡片中）
    let updated = false
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const m = messages.value[i]
      if (m.msg_type === "confirm_card" && m.metadata_json?.task_id === taskId) {
        messages.value[i] = {
          ...m,
          metadata_json: {
            ...(m.metadata_json || {}),
            task_status: status,
            done_count: done,
            total_count: total,
          },
        }
        updated = true
        break
      }
    }
    // 2) 兼容历史数据：旧的 task_card 消息仍需要更新进度
    const idx = messages.value.findIndex(
      m => m.msg_type === "task_card"
        && m.metadata_json?.task_id === taskId
        && !m.metadata_json?._task_progress
    )
    if (idx !== -1) {
      const msg = messages.value[idx]
      messages.value[idx] = {
        ...msg,
        metadata_json: {
          ...(msg.metadata_json || {}),
          task_status: status,
          done_count: done,
          total_count: total,
        },
      }
      updated = true
    }
    void updated
  }

  function startTaskMonitor(taskId: number, skillName: string) {
    if (taskMonitors.has(taskId)) return

    const intervalId = setInterval(async () => {
      try {
        const detail = await TaskAPI.getDetail(String(taskId))
        const task = detail.task

        // 更新确认消息中的任务状态（不创建进度消息）
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

  /** 为已加载的历史消息中未完成任务启动监控，同时补齐已完成/失败任务的计数
   * 兼容两种消息类型：
   * - task_card（历史数据）
   * - confirm_card 带 task_id（新逻辑：进度内嵌在确认卡片中）
   */
  async function monitorIncompleteTasks() {
    for (let i = 0; i < messages.value.length; i++) {
      const msg = messages.value[i]
      const isTaskCard = msg.msg_type === "task_card"
      const isConfirmCard = msg.msg_type === "confirm_card"
      if (!isTaskCard && !isConfirmCard) continue
      const taskId = msg.metadata_json?.task_id
      if (!taskId) continue

      // 消息中已有明确的完成/失败状态
      const ts = msg.metadata_json?.task_status
      if (ts != null && ts >= 2) {
        // 已完成/失败但缺少计数，从服务端补齐
        if ((msg.metadata_json?.done_count ?? 0) === 0 && (msg.metadata_json?.total_count ?? 0) === 0) {
          try {
            const detail = await TaskAPI.getDetail(String(taskId))
            const task = detail.task
            messages.value[i] = {
              ...msg,
              metadata_json: {
                ...(msg.metadata_json || {}),
                task_id: taskId,
                task_status: task.status,
                done_count: task.done_count,
                total_count: task.total_count,
              },
            }
          } catch { /* 静默 */ }
        }
        continue
      }

      // 未完成任务，先查询任务实际状态
      if (taskMonitors.has(taskId)) continue

      try {
        const detail = await TaskAPI.getDetail(String(taskId))
        const task = detail.task
        // 先更新当前消息的计数
        messages.value[i] = {
          ...msg,
          metadata_json: {
            ...(msg.metadata_json || {}),
            task_id: taskId,
            task_status: task.status,
            done_count: task.done_count,
            total_count: task.total_count,
          },
        }
        if (task.status >= 2) continue
        const skillName = msg.metadata_json?.skill_name || ""
        startTaskMonitor(taskId, skillName)
      } catch {
        // 静默处理
      }
    }
  }

  async function confirmCreateTask(metadata: Record<string, any>) {
    if (!activeSessionId.value) return

    const sessionId = activeSessionId.value
    const skillName = metadata.skill_name || ""
    const projectId = metadata.project_id
    const suiteId = metadata.suite_id
    const caseIds: number[] | undefined = metadata.case_ids ?? undefined
    const selectedOption = metadata._selected_option as string | undefined
    const cardSeq = (metadata.card_seq as number | null | undefined) ?? null

    try {
      const res = await ChatTaskAPI.confirmCreate(sessionId, {
        skill_name: skillName,
        project_id: projectId,
        suite_id: suiteId,
        case_ids: caseIds ?? null,
        selected_option: selectedOption ?? null,
        card_seq: cardSeq,
      })

      const taskId = res.task_id
      const total = res.total_count ?? metadata.total ?? 0

      // 回写本地 confirm_card 消息的 metadata_json，标记已确认 + 写入任务字段
      // （任务进度直接内嵌在确认卡片中，不再额外追加 task_card 消息）
      updateCardStatusInMessages(cardSeq, "confirmed", selectedOption, {
        task_id: taskId,
        task_status: 0,
        done_count: 0,
        total_count: total,
      })

      await loadSessions()

      // 启动任务状态轮询
      if (taskId) {
        startTaskMonitor(taskId, skillName)
      }

      ElMessage.success("任务已创建")
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

  /** 找到 messages 中对应的 confirm_card（card_seq 为空时回退到最后一条未处理），更新其 metadata_json */
  function updateCardStatusInMessages(
    cardSeq: number | null,
    status: string,
    selectedOption?: string,
    taskFields?: Record<string, any>,
  ) {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const m = messages.value[i]
      if (m.msg_type !== "confirm_card" || m.metadata_json?.confirm_status) continue
      // 指定了 card_seq 时必须精确匹配；未指定时取最后一条未处理的（兼容旧数据）
      if (cardSeq != null && m.metadata_json?.card_seq !== cardSeq) continue
      const meta: Record<string, any> = { ...(m.metadata_json || {}), confirm_status: status }
      if (selectedOption) meta._selected_option = selectedOption
      if (taskFields) Object.assign(meta, taskFields)
      messages.value[i] = { ...m, metadata_json: meta }
      break
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
    loadSkills,
    monitorIncompleteTasks,
    init,
  }
}
