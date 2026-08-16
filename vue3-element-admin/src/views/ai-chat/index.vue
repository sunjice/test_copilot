<template>
  <div class="ai-chat-page">
    <!-- 左侧工作区 -->
    <div class="ai-chat-workspace" :style="{ width: workspaceWidth + 'px' }">
      <div class="workspace-header">
        <span class="workspace-title">工作区</span>
        <el-button text circle size="small" @click="toggleWorkspace" :title="workspaceCollapsed ? '展开工作区' : '收起工作区'">
          <el-icon>
            <DArrowLeft v-if="!workspaceCollapsed" />
            <DArrowRight v-else />
          </el-icon>
        </el-button>
      </div>
      <WorkspacePanel v-show="!workspaceCollapsed" @context-change="onContextChange" />
    </div>

    <!-- 工作区右侧拖拽手柄 -->
    <div class="ai-chat-resizer" @mousedown="startResize"></div>

    <!-- 右侧对话区 -->
    <div class="ai-chat-main">
      <ChatPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted, onBeforeUnmount } from "vue"
import { DArrowLeft, DArrowRight } from "@element-plus/icons-vue"
import WorkspacePanel from "./workspace/WorkspacePanel.vue"
import ChatPanel from "./chat/ChatPanel.vue"
import { useAiContextStore } from "@/stores/aiContext"

const aiContextStore = useAiContextStore()

// ── 工作区折叠 ──
const workspaceCollapsed = ref(false)
const workspaceWidth = ref(400)
const MIN_WIDTH = 200
const MAX_WIDTH = 560

function toggleWorkspace() {
  workspaceCollapsed.value = !workspaceCollapsed.value
  workspaceWidth.value = workspaceCollapsed.value ? 40 : 400
}

// ── 工作区宽度拖拽 ──
let startX = 0
let startWidth = 0

function startResize(e: MouseEvent) {
  if (workspaceCollapsed.value) return
  e.preventDefault()
  startX = e.clientX
  startWidth = workspaceWidth.value
  document.addEventListener("mousemove", onResizeMove)
  document.addEventListener("mouseup", onResizeEnd)
}

function onResizeMove(e: MouseEvent) {
  const dx = e.clientX - startX
  workspaceWidth.value = Math.min(Math.max(startWidth + dx, MIN_WIDTH), MAX_WIDTH)
}

function onResizeEnd() {
  document.removeEventListener("mousemove", onResizeMove)
  document.removeEventListener("mouseup", onResizeEnd)
}

onBeforeUnmount(() => {
  document.removeEventListener("mousemove", onResizeMove)
  document.removeEventListener("mouseup", onResizeEnd)
})

// ── 工作区选择变化 → 同步到全局 aiContextStore ──
// store 内部会自动把驼峰字段转成下划线（contextJson），
// ChatPanel 监听 contextJson 注入到 pageContext，随消息发送到后端
function onContextChange(ctx: Record<string, any>) {
  aiContextStore.register("case")
  aiContextStore.update(ctx)
}

// 离开页面时清理上下文（不随会话保存）
onUnmounted(() => {
  aiContextStore.clear()
})
</script>

<style scoped>
.ai-chat-page {
  display: flex;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--el-bg-color);
}

/* 左侧工作区 */
.ai-chat-workspace {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  flex-shrink: 0;
  transition: width 0.2s;
  min-width: 0;
  overflow: hidden;
}

.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
  min-height: 36px;
}

.workspace-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

/* 工作区拖拽手柄 */
.ai-chat-resizer {
  width: 5px;
  cursor: col-resize;
  flex-shrink: 0;
  background: transparent;
  transition: background 0.15s;
  position: relative;
  z-index: 1;
}

.ai-chat-resizer:hover,
.ai-chat-resizer:active {
  background: var(--el-color-primary-light-7);
}

.ai-chat-resizer::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 3px;
  height: 32px;
  border-radius: 2px;
  background: var(--el-border-color-dark);
  opacity: 0;
  transition: opacity 0.15s;
}

.ai-chat-resizer:hover::after {
  opacity: 1;
}

/* 右侧对话区 */
.ai-chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
</style>
