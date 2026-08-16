<template>
  <div class="ai-chat-panel">
    <!-- 顶部标题栏 -->
    <div class="chat-panel-header">
      <div v-if="showHistory" class="header-title">
        <el-button text @click="showHistory = false">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <span>历史对话</span>
      </div>
      <div v-else class="header-title">
        <div class="header-logo">
          <el-icon><ChatDotRound /></el-icon>
        </div>
        <span>AI 助手</span>
      </div>
      <div class="header-actions">
        <el-button v-if="showHistory" type="danger" text size="small" @click="onDeleteAll">
          <el-icon><Delete /></el-icon>
          删除所有
        </el-button>
        <el-button v-if="!showHistory" text circle title="历史对话" @click="showHistory = true">
          <el-icon><Clock /></el-icon>
        </el-button>
        <el-button v-if="!showHistory" text circle title="新对话" @click="newSession">
          <el-icon><Plus /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 历史会话面板 -->
    <template v-if="showHistory">
      <div class="history-search-bar">
        <el-input
          v-model="historyKeyword"
          placeholder="搜索历史对话"
          clearable
          :prefix-icon="Search"
          size="small"
        />
      </div>
      <div class="history-list">
        <template v-if="groupedSessions.length">
          <div v-for="group in groupedSessions" :key="group.label" class="history-group">
            <div class="history-group-label">{{ group.label }}</div>
            <div
              v-for="s in group.sessions"
              :key="s.id!"
              class="history-item"
              @click="onHistorySelect(s.id!)"
            >
              <el-icon class="history-item-icon"><ChatDotRound /></el-icon>
              <span class="history-item-title" :title="s.title">{{ s.title }}</span>
              <span class="history-item-time">{{ formatHistoryTime(s.update_time) }}</span>
              <el-icon class="history-item-action" title="重命名" @click.stop="onRenameSession(s)"><Edit /></el-icon>
              <el-icon class="history-item-action" title="删除" @click.stop="onDeleteSession(s)"><Delete /></el-icon>
            </div>
          </div>
        </template>
        <el-empty v-else description="暂无历史对话" :image-size="50" />
      </div>
    </template>

    <!-- 正常聊天区域 -->
    <template v-else>
      <!-- 消息列表 -->
      <div
        ref="msgListRef"
        class="chat-panel-messages"
        @scroll="onMsgScroll"
      >
        <div v-if="!messages.length && !streaming" class="welcome">
          <div class="welcome-brand">
            <el-icon :size="26" color="var(--el-color-primary)"><ChatDotRound /></el-icon>
          </div>
          <h2 class="welcome-title">{{ welcomeTitle }}</h2>
          <p class="welcome-subtitle"> </p>

          <div class="quick-actions">
            <div
              v-for="q in quickActions"
              :key="q.title"
              class="quick-action-card"
              @click="onQuickSend(q)"
            >
              <div class="quick-action-icon" :style="{ background: q.bg }">
                <el-icon :size="18"><component :is="q.icon" /></el-icon>
              </div>
              <div class="quick-action-text">
                <div class="quick-action-title">{{ q.title }}</div>
                <div class="quick-action-desc">{{ q.desc }}</div>
              </div>
            </div>
          </div>
        </div>

        <ChatMessage
          v-for="(msg, idx) in messages"
          :key="msg.id || `${msg.role}-${idx}-${msg.create_time}`"
          :msg="msg"
          @view-draft="onViewDraft"
          @confirm-draft="onConfirmDraft"
          @confirm-task="onConfirmTask"
          @cancel-task="onCancelTask"
          @submit-clarify="onSubmitClarify"
          @view-task="onViewTask"
          @retry="onRetry"
        />

        <StreamingBubble
          v-if="streaming"
          :segments="segments"
        />
      </div>

      <!-- 回到底部按钮 -->
      <div v-if="showScrollBottom" class="scroll-bottom-btn" @click="scrollToBottom">
        <el-icon><ArrowDown /></el-icon>
      </div>

      <!-- 任务列表（有任务时才显示） -->
      <TaskListPanel v-if="hasTasks" :messages="messages" />

      <!-- 上下文显示行 -->
      <div v-if="showContextBar && contextBarItems.length" class="context-bar">
        <div class="context-bar-inner">
          <div class="context-info">
            <el-icon class="context-pin"><Location /></el-icon>
            <span class="context-label">上下文</span>
            <span class="context-divider">·</span>
            <span class="context-items">
              <span
                v-for="(item, idx) in contextBarItems"
                :key="idx"
                class="context-item"
              >
                <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
                <span>{{ item.label }}</span>
              </span>
            </span>
          </div>
          <el-button
            text
            circle
            size="small"
            class="context-close"
            @click="showContextBar = false"
          >
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- 输入区（上边缘可拖拽调整高度） -->
      <div
        class="chat-panel-input"
        :style="{ height: inputHeight + 'px' }"
        @mousedown="onInputMouseDown"
      >
        <!-- "/" 命令补全面板 -->
        <div v-if="showSlashPanel" class="slash-panel" @mousedown.stop>
          <template v-if="filteredSkills.length">
            <div
              v-for="(s, idx) in filteredSkills"
              :key="s.name"
              :class="['slash-item', { active: idx === slashIndex }]"
              @mouseenter="slashIndex = idx"
              @mousedown.prevent="onSlashSelect(s)"
            >
              <div class="slash-item-main">
                <span class="slash-cmd">/{{ s.name }}</span>
                <span class="slash-label">{{ skillLabel(s.name) }}</span>
              </div>
              <div class="slash-item-right">
                <span class="slash-desc" :title="s.description">{{ s.description }}</span>
                <el-tag
                  size="small"
                  effect="plain"
                  :type="s.mode === 'ASYNC' ? 'warning' : 'success'"
                  class="slash-mode-tag"
                >
                  {{ s.mode === 'ASYNC' ? '异步' : '同步' }}
                </el-tag>
              </div>
            </div>
          </template>
          <div v-else class="slash-empty">无匹配命令</div>
        </div>

        <div class="input-box">
          <el-input
            ref="inputRef"
            v-model="text"
            type="textarea"
            :placeholder="inputPlaceholder as string"
            :disabled="streaming"
            class="fill-textarea"
            @keydown="onKeydown"
          />
          <!-- 流式输出中显示停止按钮，否则显示发送按钮 -->
          <el-button
            v-if="streaming"
            class="send-btn-float stop-btn"
            type="danger"
            circle
            title="停止生成"
            @click="onStop"
          >
            <el-icon><VideoPause /></el-icon>
          </el-button>
          <el-button
            v-else
            class="send-btn-float"
            type="primary"
            circle
            :disabled="!text.trim()"
            @click="send"
          >
            <el-icon><Promotion /></el-icon>
          </el-button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, watch, nextTick, computed, onMounted } from "vue"
import { useRouter } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import type { ChatMessage as ChatMessageType } from "@/api/chat/types"
import {
  ChatDotRound, Plus, Promotion, ArrowLeft, ArrowDown, Clock, Delete, Search, Edit,
  FolderChecked, DocumentChecked, EditPen, View,
  Grid, Opportunity, Collection, Location, Close, VideoPause,
} from "@element-plus/icons-vue"
import ChatMessage from "@/layouts/components/chat/ChatMessage.vue"
import TaskListPanel from "@/layouts/components/chat/TaskListPanel.vue"
import StreamingBubble from "@/layouts/components/chat/StreamingBubble.vue"
import { useChat } from "@/layouts/components/chat/useChat"
import { useInputResize } from "@/layouts/components/chat/useChatResize"
import { formatHistoryTime } from "@/layouts/components/chat/utils"
import { useAiContextStore } from "@/stores/aiContext"
import { TASK_TYPE_MAP } from "@/views/aitc/constants"
import type { ChatSession, SkillInfo } from "@/api/chat/types"

const text = ref("")
const msgListRef = ref<HTMLElement>()

const {
  sessions,
  activeSessionId,
  messages,
  skills,
  streaming,
  segments,
  pageContext,
  createSession,
  selectSession,
  updateSession,
  deleteSession,
  sendMessage,
  stopGeneration,
  retryLastMessage,
  confirmDraft,
  confirmCreateTask,
  cancelTask,
  submitClarifyAnswers,
  viewDraft,
  init,
} = useChat()

// 是否有任务（消息 parts 里的 confirm_card part 带 task_id，或 task_card 消息）
const hasTasks = computed(() =>
  messages.value.some((m) => {
    if (m.msg_type === "task_card") return true
    const parts = m.metadata_json?.parts
    return Array.isArray(parts) && parts.some((p: any) => p?.type === "confirm_card" && p.card?.task_id != null)
  })
)

// ── 会话持久化（切页面后恢复到上次会话，保持消息和滚动位置） ──
const SESSION_KEY = "ai-chat-active-session-id"

function persistSessionId(id: number | null) {
  try {
    if (id != null) sessionStorage.setItem(SESSION_KEY, String(id))
    else sessionStorage.removeItem(SESSION_KEY)
  } catch {
    // 忽略存储异常
  }
}

function restoreSessionId(): number | null {
  try {
    const v = sessionStorage.getItem(SESSION_KEY)
    return v ? Number(v) : null
  } catch {
    return null
  }
}

// 监听会话切换，持久化
watch(activeSessionId, (id) => persistSessionId(id))

// ── 初始化 ──
onMounted(async () => {
  await init()
  // 恢复上次会话：优先 sessionStorage 记住的会话，其次第一个会话
  const savedId = restoreSessionId()
  if (savedId != null && sessions.value.some((s) => s.id === savedId)) {
    await selectSession(savedId)
  } else if (sessions.value.length > 0) {
    await selectSession(sessions.value[0].id!)
  }
  // 加载完成后滚到底部
  await nextTick()
  scrollToBottom()
})

// 暴露滚动方法，供父组件在 keep-alive 激活时调用
defineExpose({ scrollToBottom, restoreScrollPosition, saveScrollPosition })

// ── 同步上下文到 pageContext（与 LayoutChat 一致：从 aiContextStore 读取） ──
// index.vue 在工作区选择变化时已调用 aiContextStore.register/update，
// 这里监听 contextJson 变化，注入到 useChat 的 pageContext
const aiContextStore = useAiContextStore()
watch(
  () => aiContextStore.contextJson,
  (storeCtx) => {
    if (storeCtx && Object.keys(storeCtx).length) {
      pageContext.value = { ...storeCtx }
    }
  },
  { deep: true, immediate: true }
)

const router = useRouter()

function onViewTask(taskId: number) {
  if (taskId) {
    router.push(`/aitc/tasks/${taskId}`)
  } else {
    router.push("/aitc/tasks")
  }
}

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

// ── 危险确认弹窗（复用） ──
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
const slashClosed = ref(false) // Esc 关闭后，在清空/换行前不再弹出

/** 正在输入的命令关键词（仅当输入以 / 开头且未输入空格时有效） */
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
  // 文本不再以 / 开头时，重置 Esc 关闭状态
  if (!v.startsWith("/")) slashClosed.value = false
})

/** 技能命令 → 中文标签（优先使用更完整的描述） */
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
  // "/" 命令面板键盘导航
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

// ── 停止生成 ──
function onStop() {
  stopGeneration()
}

// ── 重试 ──
async function onRetry() {
  await retryLastMessage()
}

// ── 上下文显示行 ──
const showContextBar = ref(true)

const welcomeTitle = computed(() => "有什么我能帮你的吗？")

interface ContextItem {
  label: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  icon?: any
}

const contextBarItems = computed<ContextItem[]>(() => {
  const ctx = pageContext.value || {}
  const page = ctx.current_page || ""
  if (!page) return []

  const items: ContextItem[] = []

  // 公共字段：项目、模块、用例
  if (ctx.project_name || ctx.project_id) {
    items.push({ label: ctx.project_name || `项目 #${ctx.project_id}`, icon: FolderChecked })
  }
  if (ctx.suite_name || ctx.suite_id) {
    items.push({ label: ctx.suite_name || `模块 #${ctx.suite_id}`, icon: Collection })
  }
  if (ctx.current_case_id) {
    items.push({ label: `用例 #${ctx.current_case_id}`, icon: DocumentChecked })
  }

  // 页面特有字段
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

const inputPlaceholder = computed(() => {
  return `提问，或输入 "/" 触发任务命令`
})

// ── 快捷提问（Rovo 风格卡片） ──
interface QuickAction {
  title: string
  desc: string
  prompt: string
  skill: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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

// ── 草稿操作 ──
function onViewDraft(id: number) {
  viewDraft(id)
}

async function onConfirmDraft(action: string) {
  await confirmDraft(action as "confirm" | "discard")
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function onConfirmTask(metadata: Record<string, any>) {
  confirmCreateTask(metadata)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function onCancelTask(metadata: Record<string, any>) {
  cancelTask(metadata)
}

// ── 澄清卡片提交：将答案作为新消息发送给 LLM，并持久化答案状态 ──
async function onSubmitClarify(text: string, answers: Record<string, string>) {
  await sendMessage(text)
  submitClarifyAnswers(answers)
}

// ── 滚动控制 ──
const userScrolledUp = ref(false)
const showScrollBottom = ref(false)
// 滚动位置缓存（keep-alive 场景下，切走前保存，切回后恢复，保留用户停留的位置）
const savedScrollTop = ref<number | null>(null)

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

/** 保存当前滚动位置（切走前调用） */
function saveScrollPosition() {
  const el = msgListRef.value
  if (el) savedScrollTop.value = el.scrollTop
}

/** 恢复滚动位置（切回后调用） */
function restoreScrollPosition() {
  const el = msgListRef.value
  if (!el) return
  if (savedScrollTop.value != null) {
    el.scrollTop = savedScrollTop.value
  } else {
    el.scrollTop = el.scrollHeight
  }
}

// 自动滚动（用户没有手动上翻时）
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

// ── 输入区拖高 ──
const { inputHeight, onInputMouseDown } = useInputResize()
</script>

<style scoped>
.ai-chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--el-bg-color);
}

.chat-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  flex-shrink: 0;
  user-select: none;
  min-height: 44px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.header-logo {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--el-color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-logo .el-icon {
  font-size: 16px;
}

.header-actions {
  display: flex;
  gap: 0;
}

.header-actions :deep(.el-button) {
  height: 26px;
  padding: 0;
  margin: 0;
  border: none;
}

.header-actions :deep(.el-button.is-circle) {
  width: 26px;
  min-width: 26px;
}

.header-actions :deep(.el-button .el-icon) {
  font-size: 14px;
  margin: 0;
}

.header-actions :deep(.el-button--small) {
  font-size: 11px;
  height: 24px;
}

.chat-panel-messages {
  flex: 1;
  overflow-y: auto;
  padding: 2px 0;
  position: relative;
}

.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 28px 16px 16px;
  text-align: center;
  gap: 8px;
}

.welcome-brand {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--el-color-primary-light-8) 0%, var(--el-color-primary-light-9) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 2px;
  box-shadow: 0 4px 16px rgba(var(--el-color-primary-rgb), 0.12);
}

.welcome-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0;
  line-height: 1.35;
}

.welcome-subtitle {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin: 0 0 8px;
  line-height: 1.45;
}

.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 420px;
  padding: 0 4px;
}

.quick-action-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
  text-align: left;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}

.quick-action-card:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.quick-action-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--el-text-color-primary);
}

.quick-action-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.quick-action-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.quick-action-desc {
  font-size: 10px;
  color: var(--el-text-color-secondary);
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-bar {
  padding: 6px 12px 0;
  flex-shrink: 0;
}

.context-bar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 10px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
}

.context-info {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
}

.context-pin {
  font-size: 13px;
  color: var(--el-color-primary);
  flex-shrink: 0;
}

.context-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  flex-shrink: 0;
}

.context-divider {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  flex-shrink: 0;
}

.context-items {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
  overflow: hidden;
}

.context-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--el-text-color-regular);
  background: var(--el-bg-color);
  padding: 2px 8px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-lighter);
  white-space: nowrap;
  flex-shrink: 0;
}

.context-item .el-icon {
  font-size: 11px;
}

.context-close {
  flex-shrink: 0;
}

.context-close :deep(.el-icon) {
  font-size: 12px;
}

/* ── 回到底部按钮 ── */
.scroll-bottom-btn {
  position: absolute;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  transition: all 0.2s;
}

.scroll-bottom-btn:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateX(-50%) scale(1.05);
}

.scroll-bottom-btn .el-icon {
  font-size: 16px;
  color: var(--el-text-color-secondary);
}

.chat-panel-input {
  padding: 10px 12px 12px;
  flex-shrink: 0;
  overflow: visible;
  display: flex;
  flex-direction: column;
  min-height: 62px;
  position: relative;
}

.chat-panel-input::before {
  content: "";
  position: absolute;
  top: -3px;
  left: 0;
  right: 0;
  height: 7px;
  cursor: row-resize;
  z-index: 1;
}

.input-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  border-radius: 18px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  padding: 8px 46px 8px 14px;
  transition: all 0.2s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  min-height: 0;
  overflow: hidden;
}

.input-box:focus-within {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 0 0 3px var(--el-color-primary-light-8), 0 1px 3px rgba(0, 0, 0, 0.04);
}

.send-btn-float {
  position: absolute;
  right: 8px;
  bottom: 8px;
  width: 32px;
  height: 32px;
  z-index: 2;
  transition: all 0.2s;
}

.send-btn-float :deep(.el-icon) {
  font-size: 15px;
}

.send-btn-float.is-disabled {
  opacity: 0.5;
}

.stop-btn {
  animation: stopPulse 1.5s infinite;
}

@keyframes stopPulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--el-color-danger-light-5); }
  50% { box-shadow: 0 0 0 4px var(--el-color-danger-light-7); }
}

/* 历史面板 */
.history-search-bar {
  padding: 6px 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.history-group {
  margin-bottom: 2px;
}

.history-group-label {
  padding: 4px 10px;
  font-size: 10px;
  color: var(--el-text-color-secondary);
}

.history-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  cursor: pointer;
  transition: background 0.15s;
}

.history-item:hover {
  background: var(--el-fill-color-light);
}

.history-item-icon {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.history-item-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.history-item-time {
  font-size: 10px;
  color: var(--el-text-color-placeholder);
  flex-shrink: 0;
}

.history-item-action {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  cursor: pointer;
  flex-shrink: 0;
  padding: 1px;
  border-radius: 3px;
  transition: color 0.15s, background 0.15s;
  display: none;
}

.history-item:hover .history-item-action {
  display: inline-flex;
}

.history-item-action:hover {
  color: var(--el-color-primary);
  background: var(--el-fill-color);
}

.fill-textarea {
  flex: 1;
  min-height: 0;
  display: flex;
}

.fill-textarea :deep(.el-textarea) {
  flex: 1;
  min-height: 0;
  display: flex;
}

.fill-textarea :deep(.el-textarea__inner) {
  border: none;
  border-radius: 0;
  padding: 0;
  font-size: 13px;
  line-height: 1.55;
  resize: none;
  height: 100%;
  min-height: 20px;
  background: transparent;
  box-shadow: none;
}

.fill-textarea :deep(.el-textarea__inner::placeholder) {
  color: var(--el-text-color-placeholder);
}

/* ── "/" 命令补全面板 ── */
.slash-panel {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 12px;
  right: 12px;
  max-height: 260px;
  overflow-y: auto;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  box-shadow: 0 -6px 24px rgba(0, 0, 0, 0.08);
  padding: 4px;
  z-index: 20;
}

.slash-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.slash-item.active {
  background: var(--el-fill-color-light);
}

.slash-item-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.slash-cmd {
  font-size: 12px;
  font-weight: 600;
  font-family: monospace;
  color: var(--el-color-primary);
}

.slash-label {
  font-size: 12px;
  color: var(--el-text-color-primary);
}

.slash-item-right {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
  justify-content: flex-end;
}

.slash-desc {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.slash-mode-tag {
  flex-shrink: 0;
}

.slash-empty {
  padding: 10px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  text-align: center;
}
</style>
