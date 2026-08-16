<template>
  <!-- 收起状态：可拖动悬浮按钮 -->
  <div
    v-if="!isOpen"
    ref="collapsedRef"
    class="layout-chat-collapsed"
    :style="collapsedStyle"
    @mousedown="onCollapsedMouseDown"
  >
    <el-icon :size="20"><ChatDotRound /></el-icon>
    <span class="collapsed-label">AI</span>
  </div>

  <!-- 展开状态：浮窗 or 抽屉 -->
  <div
    v-else
    :class="['chat-panel', viewMode === 'drawer' ? 'chat-panel-drawer' : 'chat-panel-float']"
    :style="viewMode === 'float' ? floatStyle : { width: drawerWidth + 'px' }"
  >
    <!-- 顶部标题栏 -->
    <div
      class="chat-panel-header"
      :class="{ 'is-draggable': viewMode === 'float' }"
      @mousedown="viewMode === 'float' ? startDrag($event) : undefined"
    >
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
        <el-button v-if="!showHistory" text circle @click="showHistory = true" title="历史对话">
          <el-icon><Clock /></el-icon>
        </el-button>
        <el-button v-if="!showHistory" text circle @click="newSession" title="新对话">
          <el-icon><Plus /></el-icon>
        </el-button>
        <el-button text circle :title="viewMode === 'float' ? '切换为抽屉模式' : '切换为浮窗模式'" @click="toggleViewMode">
          <el-icon><component :is="viewMode === 'float' ? DArrowLeft : Grid" /></el-icon>
        </el-button>
        <el-button text circle title="收起" @click="toggle" >
          <el-icon><DArrowRight /></el-icon>
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
              <el-icon class="history-item-action" @click.stop="onRenameSession(s)" title="重命名"><Edit /></el-icon>
              <el-icon class="history-item-action" @click.stop="onDeleteSession(s)" title="删除"><Delete /></el-icon>
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
        class="chat-panel-messages"
        ref="msgListRef"
        @scroll="onMsgScroll"
      >
        <div v-if="!messages.length && !streaming" class="welcome">
          <div class="welcome-brand">
            <el-icon :size="26" color="var(--el-color-primary)"><ChatDotRound /></el-icon>
          </div>
          <h2 class="welcome-title">{{ welcomeTitle }}</h2>
          <!-- <p class="welcome-subtitle">我可以帮你挑选核心用例、审核质量、完善用例等</p> -->
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

        <template v-for="item in groupedMessages" :key="item.key">
          <MultiConfirmCard
            v-if="item.kind === 'confirm-group'"
            :messages="item.messages"
            @confirm-task="onConfirmTaskFromGroup"
            @cancel-task="onCancelTaskFromGroup"
          />
          <ChatMessage
            v-else
            :msg="item.msg"
            @viewDraft="onViewDraft"
            @confirmDraft="onConfirmDraft"
            @confirmTask="onConfirmTask"
            @cancelTask="onCancelTask"
            @submitClarify="onSubmitClarify"
            @retry="onRetry"
          />
        </template>

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
            @keydown="onKeydown"
            class="fill-textarea"
          />
          <!-- 流式输出中显示停止按钮，否则显示发送按钮 -->
          <el-button
            v-if="streaming"
            class="send-btn-float stop-btn"
            type="danger"
            @click="onStop"
            circle
            title="停止生成"
          >
            <el-icon><VideoPause /></el-icon>
          </el-button>
          <el-button
            v-else
            class="send-btn-float"
            type="primary"
            :disabled="!text.trim()"
            @click="send"
            circle
          >
            <el-icon><Promotion /></el-icon>
          </el-button>
        </div>
      </div>
    </template>

    <!-- 四边 + 四角隐形缩放区域（仅浮窗模式） -->
    <div v-if="viewMode === 'float'" v-for="d in RESIZE_DIRS" :key="d" :class="['resize-handle', d]" @mousedown.stop="startResize($event, d)" />

    <!-- 抽屉模式左侧宽度拖拽条 -->
    <div
      v-if="viewMode === 'drawer'"
      class="drawer-resize-handle"
      @mousedown="startDrawerResize"
    >
      <div class="dragger-bar" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, watch, nextTick, computed } from "vue"
import { useRoute } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import {
  ChatDotRound, Plus, DArrowRight, DArrowLeft, Promotion, ArrowLeft, ArrowDown, Clock, Delete, Search, Edit,
  FolderChecked, DocumentChecked, EditPen, CircleCheck, View,
  Grid, Opportunity, Collection, Location, Close, VideoPause,
} from "@element-plus/icons-vue"
import ChatMessage from "./chat/ChatMessage.vue"
import TaskListPanel from "./chat/TaskListPanel.vue"
import StreamingBubble from "./chat/StreamingBubble.vue"
import MultiConfirmCard from "./chat/MultiConfirmCard.vue"
import { useMessageGrouping } from "./chat/useMessageGrouping"
import { useChat } from "./chat/useChat"
import { useAiContextStore } from "@/stores/aiContext"
import { useChatResize, useInputResize, RESIZE_DIRS } from "./chat/useChatResize"
import { formatHistoryTime } from "./chat/utils"
import { TASK_TYPE_MAP } from "@/views/aitc/constants"
import type { ChatSession, SkillInfo } from "@/api/chat/types"

// ── 全局状态（组件实例不会被销毁，因为 LayoutMain 不会切换） ──
const isOpen = ref(false)
const viewMode = ref<'float' | 'drawer'>('drawer') // 浮窗 / 抽屉模式
const panelWidth = ref(480)
const panelHeight = ref(580)
const drawerWidth = ref(480) // 抽屉模式独立宽度
const floatX = ref(window.innerWidth - panelWidth.value - 20)
const floatY = ref(window.innerHeight - panelHeight.value - 20)
const text = ref("")
const msgListRef = ref<HTMLElement>()

// 收起态浮标可拖动位置
const collapsedTop = ref(window.innerHeight * 0.4)
const collapsedRef = ref<HTMLElement>()

const floatStyle = computed(() => ({
  width: panelWidth.value + "px",
  height: panelHeight.value + "px",
  left: floatX.value + "px",
  top: floatY.value + "px",
}))

const collapsedStyle = computed(() => ({
  top: collapsedTop.value + "px",
}))

// ── 收起态浮标拖动（拖拽和点击兼容） ──
let cStartY = 0, cStartTop = 0, cMoved = false
function onCollapsedMouseDown(e: MouseEvent) {
  cStartY = e.clientY
  cStartTop = collapsedTop.value
  cMoved = false
  document.addEventListener("mousemove", onCollapsedDrag)
  document.addEventListener("mouseup", onCollapsedUp)
}
function onCollapsedDrag(e: MouseEvent) {
  const dy = Math.abs(e.clientY - cStartY)
  if (dy > 3) cMoved = true // 超过3px算拖拽
  collapsedTop.value = Math.min(Math.max(cStartTop + (e.clientY - cStartY), 60), window.innerHeight - 120)
}
function onCollapsedUp() {
  document.removeEventListener("mousemove", onCollapsedDrag)
  document.removeEventListener("mouseup", onCollapsedUp)
  if (!cMoved) toggle() // 没移动过 = 点击打开
}

const route = useRoute()
const aiContextStore = useAiContextStore()

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

// 是否有任务消息
const hasTasks = computed(() =>
  messages.value.some((m) => m.msg_type === "task_card")
)

// ── 消息分组：连续的 assistant confirm_card 合并渲染（共享逻辑） ──
const groupedMessages = useMessageGrouping(messages)

// ── 初始化（只执行一次） ──
const inited = ref(false)
function ensureInit() {
  if (inited.value) return
  inited.value = true
  init()
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

// ── 控制开关 ──
function toggle() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    ensureInit()
    if (!activeSessionId.value && sessions.value.length > 0) {
      selectSession(sessions.value[0].id!)
    }
  }
}

/** 浮窗 ↔ 抽屉切换 */
function toggleViewMode() {
  viewMode.value = viewMode.value === 'float' ? 'drawer' : 'float'
}

// ── 抽屉左侧宽度拖拽 ──
const MIN_DRAWER_W = 320, MAX_DRAWER_W = 840
let dwStartX = 0, dwStartW = 0
function startDrawerResize(e: MouseEvent) {
  e.preventDefault()
  dwStartX = e.clientX
  dwStartW = drawerWidth.value
  document.addEventListener("mousemove", onDrawerResizeMove)
  document.addEventListener("mouseup", onDrawerResizeEnd)
}
function onDrawerResizeMove(e: MouseEvent) {
  const dx = dwStartX - e.clientX // 向左拖 = 变宽
  drawerWidth.value = Math.min(Math.max(dwStartW + dx, MIN_DRAWER_W), MAX_DRAWER_W)
}
function onDrawerResizeEnd() {
  document.removeEventListener("mousemove", onDrawerResizeMove)
  document.removeEventListener("mouseup", onDrawerResizeEnd)
}

// ── 监听路由/Store，同步页面上下文（route query 优先） ──
watch(
  [() => route.fullPath, () => aiContextStore.contextJson],
  ([, storeCtx]) => {
    const ctx: Record<string, any> = {}
    const { projectId, suiteId } = route.query
    if (projectId) ctx.project_id = Number(projectId)
    if (suiteId) ctx.suite_id = Number(suiteId)
    if (route.meta?.projectId) ctx.project_id = Number(route.meta.projectId)
    // Store 里的 current_page / project_id / suite_id 等始终合并进来
    // route.query 优先级更高（已设置过的字段不再被 Store 覆盖）
    if (storeCtx && Object.keys(storeCtx).length) {
      Object.assign(ctx, storeCtx, ctx)
    }
    if (Object.keys(ctx).length) {
      pageContext.value = ctx
    }
  },
  { deep: true, immediate: true }
)

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

const welcomeTitle = computed(() => {
  // const hour = new Date().getHours()
  // let greet: string
  // if (hour < 12) greet = "早上好"
  // else if (hour < 18) greet = "下午好"
  // else greet = "晚上好"
  // return `${greet}，有什么我能帮你的吗？`
  return "有什么我能帮你的吗？"
})

interface ContextItem {
  label: string
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

function onConfirmTask(metadata: Record<string, any>) {
  confirmCreateTask(metadata)
}

function onCancelTask(metadata: Record<string, any>) {
  cancelTask(metadata)
}

// ── 合并卡片（MultiConfirmCard）事件转发 ──
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function onConfirmTaskFromGroup(_msg: any, metadata: Record<string, any>) {
  confirmCreateTask(metadata)
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function onCancelTaskFromGroup(_msg: any, metadata: Record<string, any>) {
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
// const scrollThrottle = ref(false)

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

// 自动滚动（用户没有手动上翻时）
// 监听末区块内容长度：打字机效果是追加到末尾 text/thinking 区块，数组长度不变，需监听内容变化
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

// ── 浮窗拖拽 + 缩放 ──
const { startDrag, startResize } = useChatResize(panelWidth, panelHeight, floatX, floatY)
const { inputHeight, onInputMouseDown } = useInputResize()

// ── 对外暴露开关方法（给 LayoutToolbar 用） ──
defineExpose({ toggle, isOpen })
</script>

<style scoped>
/* ── 收起态：右侧可拖动悬浮按钮 ── */
.layout-chat-collapsed {
  position: fixed;
  right: 0;
  width: 36px;
  padding: 12px 0;
  background: var(--el-color-primary);
  color: #fff;
  border-radius: 8px 0 0 8px;
  cursor: grab;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  z-index: 2000;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.15);
  transition: width 0.2s, box-shadow 0.2s;
  user-select: none;
}

.layout-chat-collapsed:active {
  cursor: grabbing;
}

.layout-chat-collapsed:hover {
  width: 40px;
  box-shadow: -2px 0 12px rgba(0, 0, 0, 0.25);
}

.collapsed-label {
  font-size: 11px;
  writing-mode: vertical-rl;
  letter-spacing: 2px;
  pointer-events: none;
}

/* ── 展开态共用基类 ── */
.chat-panel {
  position: fixed;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  display: flex;
  flex-direction: column;
  z-index: 2000;
  overflow: hidden;
}

/* ── 浮窗模式 ── */
.chat-panel-float {
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.1), 0 4px 12px rgba(0, 0, 0, 0.04);
  transition: box-shadow 0.2s;
}

.chat-panel-float:hover {
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.12), 0 6px 16px rgba(0, 0, 0, 0.05);
}

/* ── 抽屉模式：右侧全高面板 ── */
.chat-panel-drawer {
  right: 0;
  top: 0;
  bottom: 0;
  border-radius: 0;
  border-right: none;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.1);
  animation: slideInRight 0.25s ease-out;
}

/* ── 抽屉模式左侧拖拽条 ── */
.drawer-resize-handle {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 6px;
  cursor: col-resize;
  z-index: 11;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.drawer-resize-handle:hover {
  background: rgba(var(--el-color-primary-rgb, 64 158 255), 0.12);
}

.drawer-resize-handle:active {
  background: rgba(var(--el-color-primary-rgb, 64 158 255), 0.22);
}

.dragger-bar {
  width: 3px;
  height: 32px;
  border-radius: 2px;
  background: var(--el-border-color-dark);
  opacity: 0;
  transition: opacity 0.15s;
}

.drawer-resize-handle:hover .dragger-bar {
  opacity: 1;
}

@keyframes slideInRight {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

/* 缩放热区 */
.resize-handle { position: absolute; }

.resize-handle.top, .resize-handle.bottom { height: 6px; left: 12px; right: 12px; cursor: ns-resize; }
.resize-handle.left, .resize-handle.right { width: 6px; top: 12px; bottom: 12px; cursor: ew-resize; }
.resize-handle.top { top: 0; }
.resize-handle.bottom { bottom: 0; z-index: 9; }
.resize-handle.left { left: 0; z-index: 9; }
.resize-handle.right { right: 0; z-index: 9; }

.resize-handle.tl, .resize-handle.tr, .resize-handle.bl, .resize-handle.br { width: 12px; height: 12px; z-index: 10; }
.resize-handle.tl { top: 0; left: 0; cursor: nwse-resize; }
.resize-handle.tr { top: 0; right: 0; cursor: nesw-resize; }
.resize-handle.bl { bottom: 0; left: 0; cursor: nesw-resize; }
.resize-handle.br { bottom: 0; right: 0; cursor: nwse-resize; }

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

.chat-panel-header.is-draggable {
  cursor: move;
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

.context-item .el-icon {
  font-size: 11px;
}

.context-close {
  padding: 6px 12px 0;
  flex-shrink: 0;
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
