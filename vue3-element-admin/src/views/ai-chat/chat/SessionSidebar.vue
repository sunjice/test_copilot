<template>
  <aside class="session-sidebar">
    <!-- 新建对话按钮 -->
    <div class="sidebar-top">
      <el-button class="new-chat-btn" type="primary" @click="onNewChat">
        <el-icon><Plus /></el-icon>
        新建对话
      </el-button>

      <!-- 搜索框 -->
      <el-input
        v-model="historyKeyword"
        placeholder="搜索历史对话"
        clearable
        :prefix-icon="Search"
        size="small"
        class="search-input"
      />
    </div>

    <!-- 会话列表（按时间倒序平铺，无分组） -->
    <div class="session-list">
      <template v-if="filteredSessions.length">
        <div
          v-for="s in filteredSessions"
          :key="s.id!"
          :class="['session-item', { active: activeSessionId === s.id }]"
          @click="onSelect(s.id!)"
        >
          <el-icon class="session-item-icon"><ChatDotRound /></el-icon>
          <span class="session-item-title" :title="s.title">{{ s.title }}</span>
          <el-icon class="session-item-action" title="重命名" @click.stop="onRename(s)"><Edit /></el-icon>
          <el-icon class="session-item-action" title="删除" @click.stop="onDelete(s)"><Delete /></el-icon>
        </div>
      </template>
      <el-empty v-else description="暂无历史对话" :image-size="50" />
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { Plus, Search, ChatDotRound, Edit, Delete } from "@element-plus/icons-vue"
import type { ChatSession } from "@/api/chat/types"

const props = defineProps<{
  sessions: ChatSession[]
  activeSessionId: number | null
}>()

const emit = defineEmits<{
  (e: "new-chat"): void
  (e: "select", id: number): void
  (e: "rename", id: number, title: string): void
  (e: "delete", id: number): void
}>()

// 搜索关键字
const historyKeyword = ref("")

// 按标题过滤 + 按 update_time 倒序平铺
const filteredSessions = computed(() => {
  const k = historyKeyword.value.trim().toLowerCase()
  const list = props.sessions.filter((s) =>
    k ? s.title?.toLowerCase().includes(k) : true
  )
  return [...list].sort((a, b) => {
    const ta = a.update_time ? new Date(a.update_time).getTime() : 0
    const tb = b.update_time ? new Date(b.update_time).getTime() : 0
    return tb - ta
  })
})

function onNewChat() {
  emit("new-chat")
}

function onSelect(id: number) {
  emit("select", id)
}

async function onRename(s: ChatSession) {
  try {
    const { value } = await ElMessageBox.prompt("请输入新名称", "重命名对话", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      inputValue: s.title,
      inputPlaceholder: "对话名称",
    })
    if (value && value.trim() && value.trim() !== s.title) {
      emit("rename", s.id!, value.trim())
    }
  } catch {
    // 取消
  }
}

async function onDelete(s: ChatSession) {
  try {
    await ElMessageBox.confirm(`确定删除"${s.title}"？此操作不可恢复。`, "确认删除", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    })
  } catch {
    return
  }
  emit("delete", s.id!)
  ElMessage.success("已删除")
}
</script>

<style scoped>
.session-sidebar {
  display: flex;
  flex-direction: column;
  width: 240px;
  height: 100%;
  min-height: 0;
  flex-shrink: 0;
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-lighter);
}

.sidebar-top {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.new-chat-btn {
  width: 100%;
}

.new-chat-btn :deep(.el-icon) {
  margin-right: 4px;
}

.search-input {
  width: 100%;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 12px;
  cursor: pointer;
  transition: background 0.15s;
  user-select: none;
}

.session-item:hover {
  background: var(--el-fill-color-light);
}

.session-item.active {
  background: var(--el-color-primary-light-9);
}

.session-item-icon {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.session-item.active .session-item-icon {
  color: var(--el-color-primary);
}

.session-item-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.session-item.active .session-item-title {
  color: var(--el-color-primary);
  font-weight: 500;
}

.session-item-time {
  font-size: 10px;
  color: var(--el-text-color-placeholder);
  flex-shrink: 0;
}

.session-item-action {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  cursor: pointer;
  flex-shrink: 0;
  padding: 1px;
  border-radius: 3px;
  transition: color 0.15s, background 0.15s;
  display: none;
}

.session-item:hover .session-item-action {
  display: inline-flex;
}

.session-item-action:hover {
  color: var(--el-color-primary);
  background: var(--el-fill-color);
}
</style>
