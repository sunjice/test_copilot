<template>
  <div class="task-list-panel">
    <div class="task-list-header" @click="expanded = !expanded">
      <div class="task-list-title">
        <el-icon><List /></el-icon>
        <span>任务列表</span>
        <span v-if="tasks.length" class="task-count-badge">{{ doneCount }}/{{ tasks.length }}</span>
      </div>
      <el-icon class="task-list-arrow" :class="{ 'is-expanded': expanded }">
        <ArrowDown />
      </el-icon>
    </div>

    <div v-show="expanded" class="task-list-body">
      <div v-if="!tasks.length" class="task-empty">暂无任务</div>
      <div
        v-for="task in tasks"
        :key="task.taskId"
        class="task-item"
        @click="goTaskDetail(task.taskId)"
      >
        <div class="task-item-info">
          <!-- 已完成：圈中带勾 -->
          <svg v-if="task.status === 2" class="task-status-icon" width="14" height="14" viewBox="0 0 14 14" :style="{ color: statusColor(task.status) }">
            <circle cx="7" cy="7" r="6.5" fill="currentColor"/>
            <polyline points="4,7 6,9.5 10,5" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <!-- 失败：圈中带感叹号 -->
          <svg v-else-if="task.status === 3" class="task-status-icon" width="14" height="14" viewBox="0 0 14 14" :style="{ color: statusColor(task.status) }">
            <circle cx="7" cy="7" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/>
            <line x1="7" y1="4" x2="7" y2="8.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="7" cy="10.5" r="0.8" fill="currentColor"/>
          </svg>
          <!-- 未开始：空圈 -->
          <svg v-else-if="task.status === 0" class="task-status-icon" width="14" height="14" viewBox="0 0 14 14" :style="{ color: statusColor(task.status) }">
            <circle cx="7" cy="7" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/>
          </svg>
          <!-- 在做：圈中带 ▶ -->
          <svg v-else class="task-status-icon" width="14" height="14" viewBox="0 0 14 14" :style="{ color: statusColor(task.status) }">
            <circle cx="7" cy="7" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/>
            <polygon points="5.5,4 5.5,10 10.2,7" fill="currentColor"/>
          </svg>
          <span class="task-item-label">{{ task.label }}</span>
        </div>
        <div class="task-item-meta">
          <span class="task-progress" :class="progressClass(task)">
            {{ task.done }}/{{ task.total }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { List, ArrowDown } from "@element-plus/icons-vue"
import type { ChatMessage } from "@/api/chat/types"
import { TASK_TYPE_MAP } from "@/views/aitc/constants"

const props = defineProps<{
  messages: ChatMessage[]
}>()

const router = useRouter()
const expanded = ref(false)

interface TaskItem {
  taskId: number
  label: string
  status: number
  done: number
  total: number
}

const tasks = computed(() => {
  const seen = new Set<number>()
  const list: TaskItem[] = []

  for (const msg of props.messages) {
    // 兼容两种消息类型：task_card（历史数据）、confirm_card 内嵌任务（新逻辑）
    const isTaskCard = msg.msg_type === "task_card"
    const isConfirmCard = msg.msg_type === "confirm_card"
    if (!isTaskCard && !isConfirmCard) continue
    const meta = msg.metadata_json
    if (!meta?.task_id) continue
    if (seen.has(meta.task_id)) continue
    seen.add(meta.task_id)

    // confirm_card 需要已确认才展示在任务列表
    if (isConfirmCard && meta.confirm_status !== "confirmed") continue

    list.push({
      taskId: meta.task_id,
      label: TASK_TYPE_MAP[meta.skill_name]?.label || meta.skill_name || "任务",
      status: meta.task_status ?? 0,
      done: meta.done_count ?? 0,
      total: meta.total_count ?? meta.total ?? 0,
    })
  }

  return list
})

const doneCount = computed(() =>
  tasks.value.filter((t) => t.status === 2).length
)

function statusColor(status: number) {
  if (status === 2) return "var(--el-color-success)"
  if (status === 3) return "var(--el-color-danger)"
  if (status === 0 || status === 1) return "var(--el-color-primary)"
  return "var(--el-text-color-placeholder)"
}

function progressClass(task: TaskItem) {
  if (task.status === 2) return "is-done"
  if (task.status === 3) return "is-failed"
  return "is-running"
}

function goTaskDetail(taskId: number) {
  router.push(`/aitc/tasks/${taskId}`)
}
</script>

<style scoped>
.task-list-panel {
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  flex-shrink: 0;
}

.task-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.task-list-header:hover {
  background: var(--el-fill-color-light);
}

.task-list-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.task-list-arrow {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  transition: transform 0.2s;
}

.task-list-arrow.is-expanded {
  transform: rotate(180deg);
}

.task-list-body {
  padding: 0 12px 8px;
  max-height: 200px;
  overflow-y: auto;
}

.task-empty {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  padding: 8px 0;
  text-align: center;
}

.task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.task-item:hover {
  background: var(--el-fill-color-light);
}

.task-item-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--el-text-color-primary);
}

.task-status-icon {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
}

.task-item-label {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-item-meta {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.task-progress {
  font-weight: 500;
}

.task-progress.is-running {
  color: var(--el-color-primary);
}

.task-progress.is-done {
  color: var(--el-color-success);
}

.task-progress.is-failed {
  color: var(--el-color-danger);
}

.task-count-badge {
  font-size: 11px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  padding: 1px 6px;
  border-radius: 10px;
  font-weight: 500;
}
</style>
