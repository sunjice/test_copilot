import { ref, shallowRef, watch, nextTick, computed, type Ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import {
  FolderChecked, DocumentChecked, EditPen, View, Search,
  Grid, Opportunity, Collection,
} from "@element-plus/icons-vue"
import { TASK_TYPE_MAP } from "@/views/aitc/constants"
import type { ChatSession, SkillInfo, Part } from "@/api/chat/types"

/**
 * 聊天面板公共逻辑（LayoutChat 与 ai-chat/ChatPanel 共用）。
 * 抽取两个界面重复的「聊天主体」逻辑：历史面板、"/"命令补全、
 * 发送/停止/重试、上下文显示、快捷卡片、会话操作、滚动控制。
 *
 * @param deps 由外部注入的依赖（useChat 的 state/actions + 本地 ref）
 */
export function useChatPanel(deps: {
  // useChat 状态
  sessions: Ref<ChatSession[]>
  activeSessionId: Ref<number | null>
  messages: Ref<any[]>
  skills: Ref<SkillInfo[]>
  streaming: Ref<boolean>
  segments: Ref<Part[]>
  pageContext: Ref<Record<string, any>>
  // useChat actions
  createSession: () => Promise<any>
  selectSession: (id: number) => Promise<void>
  updateSession: (id: number, data: Record<string, any>) => Promise<void>
  deleteSession: (id: number) => Promise<void>
  sendMessage: (text: string, skill?: string) => Promise<void>
  stopGeneration: () => void
  retryLastMessage: () => Promise<void>
  confirmDraft: (action: "confirm" | "discard") => Promise<void>
  confirmCreateTask: (metadata: Record<string, any>) => Promise<void>
  cancelTask: (metadata: Record<string, any>) => Promise<void>
  submitClarifyAnswers: (answers: Record<string, string>) => void
  cancelClarify: () => void
  viewDraft: (id: number) => void
  // 本地 ref
  text: Ref<string>
  msgListRef: Ref<HTMLElement | undefined>
}) {
  const {
    sessions, activeSessionId, messages, skills, streaming, segments, pageContext,
    createSession, selectSession, updateSession, deleteSession,
    sendMessage, stopGeneration, retryLastMessage, confirmDraft, confirmCreateTask, cancelTask,
    submitClarifyAnswers, cancelClarify, viewDraft,
    text, msgListRef,
  } = deps

  // ── 历史面板 ──
  const showHistory = ref(false)
  const historyKeyword = ref("")

  const filteredSessions = computed(() => {
    if (!historyKeyword.value.trim()) return sessions.value
    const k = historyKeyword.value.trim().toLowerCase()
    return sessions.value.filter((s) => s.title?.toLowerCase().includes(k))
  })

  const groupedSessions = computed(() => {
    const groups: { label: string; sessions: ChatSession[] }[] = []
    const now = new Date()
    now.setHours(0, 0, 0, 0)
    const yesterday = new Date(now)
    yesterday.setDate(yesterday.getDate() - 1)
    const weekAgo = new Date(now)
    weekAgo.setDate(weekAgo.getDate() - 7)
    const monthAgo = new Date(now)
    monthAgo.setMonth(monthAgo.getMonth() - 1)

    const today: ChatSession[] = []
    const yday: ChatSession[] = []
    const week: ChatSession[] = []
    const month: ChatSession[] = []
    const earlier: ChatSession[] = []

    for (const s of filteredSessions.value) {
      const t = s.update_time ? new Date(s.update_time) : null
      if (!t) { earlier.push(s); continue }
      const d = new Date(t); d.setHours(0, 0, 0, 0)
      if (d.getTime() === now.getTime()) today.push(s)
      else if (d.getTime() === yesterday.getTime()) yday.push(s)
      else if (d.getTime() > weekAgo.getTime()) week.push(s)
      else if (d.getTime() > monthAgo.getTime()) month.push(s)
      else earlier.push(s)
    }

    if (today.length) groups.push({ label: "今天", sessions: today })
    if (yday.length) groups.push({ label: "昨天", sessions: yday })
    if (week.length) groups.push({ label: "最近7天", sessions: week })
    if (month.length) groups.push({ label: "最近30天", sessions: month })
    if (earlier.length) groups.push({ label: "更早", sessions: earlier })
    return groups
  })

  function onHistorySelect(sessionId: number) {
    showHistory.value = false
    selectSession(sessionId)
  }

  async function onRenameSession(s: ChatSession) {
    try {
      const { value } = await ElMessageBox.prompt("请输入新名称", "重命名对话", {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        inputValue: s.title,
        inputPlaceholder: "对话名称",
      })
      if (value && value.trim() && value.trim() !== s.title) {
        await updateSession(s.id!, { title: value.trim() })
      }
    } catch {
      // 取消
    }
  }

  async function confirmDanger(message: string): Promise<boolean> {
    try {
      await ElMessageBox.confirm(message, "确认删除", {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      })
      return true
    } catch {
      return false
    }
  }

  async function onDeleteSession(s: ChatSession) {
    if (!(await confirmDanger(`确定删除"${s.title}"？此操作不可恢复。`))) return
    if (activeSessionId.value === s.id) {
      const rest = sessions.value.filter((x) => x.id !== s.id)
      if (rest.length) await selectSession(rest[0].id!)
    }
    await deleteSession(s.id!)
    ElMessage.success("已删除")
  }

  async function onDeleteAll() {
    if (!sessions.value.length) return
    if (!(await confirmDanger("确定删除所有历史对话？此操作不可恢复。"))) return
    const ids = sessions.value.map((s) => s.id).filter((id): id is number => !!id)
    await Promise.all(ids.map((id) => deleteSession(id)))
    ElMessage.success("已删除所有历史对话")
    showHistory.value = false
  }

  // ── 发送消息 ──
  const slashClosed = ref(false)

  async function send() {
    const val = text.value.trim()
    if (!val || streaming.value) return
    text.value = ""
    slashClosed.value = false
    await sendMessage(val)
  }

  // ── "/" 命令补全 ──
  const inputRef = ref()
  const slashIndex = ref(0)

  const slashKeyword = computed(() => {
    const t = text.value
    if (!t.startsWith("/")) return null
    const cmd = t.slice(1)
    if (/\s/.test(cmd)) return null
    return cmd.toLowerCase()
  })

  const filteredSkills = computed(() => {
    const kw = slashKeyword.value
    if (kw === null) return []
    return skills.value.filter((s) => s.name.toLowerCase().startsWith(kw))
  })

  const showSlashPanel = computed(
    () => slashKeyword.value !== null && !slashClosed.value && !streaming.value
  )

  watch(slashKeyword, () => {
    slashIndex.value = 0
  })

  watch(text, (v) => {
    if (!v.startsWith("/")) slashClosed.value = false
  })

  const SKILL_LABELS: Record<string, string> = {
    core_select: "挑选核心用例",
    case_review: "审核用例质量",
    script_gen: "生成测试脚本",
    case_complete: "完善测试用例",
    case_design: "设计测试用例",
  }

  function skillLabel(name: string): string {
    return SKILL_LABELS[name] || TASK_TYPE_MAP[name]?.label || name
  }

  function onSlashSelect(s: SkillInfo) {
    text.value = `/${s.name} `
    slashClosed.value = false
    nextTick(() => inputRef.value?.focus())
  }

  function onKeydown(e: Event | KeyboardEvent) {
    if (!(e instanceof KeyboardEvent)) return
    if (showSlashPanel.value && filteredSkills.value.length) {
      if (e.key === "ArrowDown") {
        e.preventDefault()
        slashIndex.value = (slashIndex.value + 1) % filteredSkills.value.length
        return
      }
      if (e.key === "ArrowUp") {
        e.preventDefault()
        slashIndex.value = (slashIndex.value - 1 + filteredSkills.value.length) % filteredSkills.value.length
        return
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault()
        onSlashSelect(filteredSkills.value[slashIndex.value])
        return
      }
      if (e.key === "Escape") {
        slashClosed.value = true
        return
      }
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  // ── 停止 / 重试 ──
  function onStop() {
    stopGeneration()
  }
  async function onRetry() {
    await retryLastMessage()
  }

  // ── 上下文显示行 ──
  const showContextBar = ref(true)
  const welcomeTitle = computed(() => "有什么我能帮你的吗？")

  interface ContextItem {
    label: string
    icon?: any
  }

  const contextBarItems = computed<ContextItem[]>(() => {
    const ctx = pageContext.value || {}
    const page = ctx.current_page || ""
    if (!page) return []

    const items: ContextItem[] = []
    if (ctx.project_name || ctx.project_id) {
      items.push({ label: ctx.project_name || `项目 #${ctx.project_id}`, icon: FolderChecked })
    }
    if (ctx.suite_name || ctx.suite_id) {
      items.push({ label: ctx.suite_name || `模块 #${ctx.suite_id}`, icon: Collection })
    }
    if (ctx.current_case_id) {
      items.push({ label: `用例 #${ctx.current_case_id}`, icon: DocumentChecked })
    }
    if (page === "case") {
      if (ctx.selected_case_ids?.length) {
        items.push({ label: `已选 ${ctx.selected_case_ids.length} 条用例`, icon: Grid })
      }
    } else {
      if (ctx.task_id) items.push({ label: `任务 #${ctx.task_id}`, icon: Opportunity })
      if (ctx.script_id) items.push({ label: `脚本 #${ctx.script_id}`, icon: DocumentChecked })
    }
    return items
  })

  const inputPlaceholder = computed(() => `提问，或输入 "/" 触发任务命令`)

  // ── 快捷提问卡片 ──
  interface QuickAction {
    title: string
    desc: string
    prompt: string
    skill: string
    icon: any
    bg: string
  }

  const quickActions = shallowRef<QuickAction[]>([
    {
      title: "挑选核心用例",
      desc: "从当前模块智能挑选最重要的用例",
      prompt: "/core_select 帮我挑选核心用例",
      skill: "core_select",
      icon: Search,
      bg: "linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%)",
    },
    {
      title: "审核用例质量",
      desc: "检查字段完整性和步骤规范性",
      prompt: "/case_review 审核用例质量",
      skill: "case_review",
      icon: View,
      bg: "linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%)",
    },
    {
      title: "完善测试用例",
      desc: "自动补全用例的缺失字段和测试步骤",
      prompt: "/case_complete 完善测试用例",
      skill: "case_complete",
      icon: EditPen,
      bg: "linear-gradient(135deg, #ffedd5 0%, #fed7aa 100%)",
    },
  ])

  async function onQuickSend(action: QuickAction) {
    if (streaming.value) return
    await sendMessage(action.prompt, action.skill)
  }

  // ── 会话操作 ──
  async function newSession() {
    const s = await createSession()
    await selectSession(s.id!)
  }

  // ── 草稿 / 任务 / 澄清事件 ──
  function onViewDraft(id: number) {
    viewDraft(id)
  }
  async function onConfirmDraft(action: string) {
    await confirmDraft(action as "confirm" | "discard")
  }
  function onConfirmTask(metadata: Record<string, any>) {
    confirmCreateTask(metadata)
  }
  function onCancelTask(metadata: Record<string, any>) {
    cancelTask(metadata)
  }
  async function onSubmitClarify(text: string, answers: Record<string, string>) {
    await sendMessage(text)
    submitClarifyAnswers(answers)
  }
  function onCancelClarify() {
    cancelClarify()
  }

  // ── 滚动控制 ──
  const userScrolledUp = ref(false)
  const showScrollBottom = ref(false)

  function onMsgScroll() {
    const el = msgListRef.value
    if (!el) return
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight
    userScrolledUp.value = dist > 80
    showScrollBottom.value = dist > 120
  }

  function scrollToBottom() {
    const el = msgListRef.value
    if (!el) return
    el.scrollTop = el.scrollHeight
    userScrolledUp.value = false
    showScrollBottom.value = false
  }

  const lastSegContentLen = computed(() => {
    const last = segments.value[segments.value.length - 1]
    if (!last) return 0
    return (last.type === "text" || last.type === "thinking") ? last.content.length : 0
  })

  watch(
    () => [messages.value.length, segments.value.length, lastSegContentLen.value],
    async () => {
      await nextTick()
      if (!userScrolledUp.value && msgListRef.value) {
        msgListRef.value.scrollTop = msgListRef.value.scrollHeight
      }
    }
  )

  return {
    // 历史面板
    showHistory, historyKeyword, filteredSessions, groupedSessions,
    onHistorySelect, onRenameSession, onDeleteSession, onDeleteAll,
    // 命令补全
    inputRef, slashIndex, slashKeyword, filteredSkills, showSlashPanel,
    skillLabel, onSlashSelect, onKeydown,
    // 发送/停止/重试
    send, onStop, onRetry,
    // 上下文
    showContextBar, welcomeTitle, contextBarItems, inputPlaceholder,
    // 快捷卡片
    quickActions, onQuickSend,
    // 会话操作
    newSession,
    // 草稿/任务/澄清
    onViewDraft, onConfirmDraft, onConfirmTask, onCancelTask, onSubmitClarify, onCancelClarify,
    // 滚动
    userScrolledUp, showScrollBottom, onMsgScroll, scrollToBottom,
  }
}
