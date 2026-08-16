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
import { ref, watch, nextTick, computed } from "vue"
import { useRoute, useRouter } from "vue-router"
import {
  ChatDotRound, Plus, DArrowRight, DArrowLeft, Promotion, ArrowLeft, ArrowDown, Clock, Delete, Search, Edit,
  Grid, Location, Close, VideoPause,
} from "@element-plus/icons-vue"
import ChatMessage from "./chat/ChatMessage.vue"
import TaskListPanel from "./chat/TaskListPanel.vue"
import StreamingBubble from "./chat/StreamingBubble.vue"
import { useChat } from "./chat/useChat"
import { useChatPanel } from "./chat/useChatPanel"
import { useAiContextStore } from "@/stores/aiContext"
import { useChatResize, useInputResize, RESIZE_DIRS } from "./chat/useChatResize"
import { formatHistoryTime } from "./chat/utils"

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
const router = useRouter()
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
  reset: resetChat,
} = useChat()

// ── 聊天主体公共逻辑（历史面板/命令补全/发送/上下文/快捷卡片/会话操作/滚动） ──
const {
  showHistory, historyKeyword, filteredSessions, groupedSessions,
  onHistorySelect, onRenameSession, onDeleteSession, onDeleteAll,
  inputRef, slashIndex, slashKeyword, filteredSkills, showSlashPanel,
  skillLabel, onSlashSelect, onKeydown,
  send, onStop, onRetry,
  showContextBar, welcomeTitle, contextBarItems, inputPlaceholder,
  quickActions, onQuickSend,
  newSession,
  onViewDraft, onConfirmDraft, onConfirmTask, onCancelTask, onSubmitClarify,
  userScrolledUp, showScrollBottom, onMsgScroll, scrollToBottom,
} = useChatPanel({
  sessions, activeSessionId, messages, skills, streaming, segments, pageContext,
  createSession, selectSession, updateSession, deleteSession,
  sendMessage, stopGeneration, retryLastMessage, confirmDraft, confirmCreateTask, cancelTask,
  submitClarifyAnswers, viewDraft,
  text, msgListRef,
})

// 是否有任务（消息 parts 里的 confirm_card part 带 task_id，或 task_card 消息）
const hasTasks = computed(() =>
  messages.value.some((m) => {
    if (m.msg_type === "task_card") return true
    const parts = m.metadata_json?.parts
    return Array.isArray(parts) && parts.some((p: any) => p?.type === "confirm_card" && p.card?.task_id != null)
  })
)

// ── 初始化（只执行一次） ──
const inited = ref(false)
function ensureInit() {
  if (inited.value) return
  inited.value = true
  init()
}

// ── 退出登录重置：路由切到 /login 时清空聊天内存态 ──
watch(
  () => route.path,
  (path) => {
    if (path === "/login") {
      resetChat()
      inited.value = false
      isOpen.value = false
      showHistory.value = false
      text.value = ""
    }
  }
)

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

function onViewTask(taskId: number) {
  if (taskId) {
    router.push(`/aitc/tasks/${taskId}`)
  } else {
    router.push("/aitc/tasks")
  }
}

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
