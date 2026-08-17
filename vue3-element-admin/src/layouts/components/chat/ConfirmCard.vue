<template>
  <!-- 单个确认卡片（confirm_card part），横排紧凑展示 -->
  <div class="confirm-card" :class="[`state-${state}`]">
    <div class="confirm-card-body">
      <!-- 左侧：信息 chip 横排（前面带"创建任务："提示） -->
      <div v-if="hasStructured" class="confirm-chips">
        <span class="confirm-card-tag">创建任务：</span>
        <span v-if="card.project_name" class="chip">
          <span class="chip-label">项目</span>
          <span class="chip-value">{{ card.project_name }}</span>
        </span>
        <span v-if="suiteDisplay" class="chip">
          <span class="chip-label">模块</span>
          <span class="chip-value">{{ suiteDisplay }}</span>
        </span>
        <span v-if="taskLabel" class="chip">
          <span class="chip-label">任务类型</span>
          <span class="chip-value">{{ taskLabel }}</span>
        </span>
        <span v-if="card.total != null" class="chip">
          <span class="chip-label">用例数量</span>
          <span class="chip-value">{{ card.total }} 条</span>
        </span>
      </div>

      <!-- 右侧：确认/取消 按钮（同行） -->
      <div v-if="state === 'idle'" class="confirm-actions-inline">
        <el-button
          size="small"
          type="primary"
          :loading="confirming"
          @click="onConfirm"
        >
          确认
        </el-button>
        <el-button size="small" plain @click="onCancel">取消</el-button>
      </div>
      <div v-else-if="state === 'confirmed'" class="confirm-confirmed-inline">
        <span class="task-status-tag" :class="`status-${taskStatus}`">
          {{ taskStatusLabel }}
        </span>
        <el-button
          size="small"
          type="primary"
          plain
          @click="onViewTask"
        >
          {{ taskButtonText }}
        </el-button>
      </div>
      <div v-else class="confirm-result-inline muted">已取消</div>
    </div>

    <!-- confirmed 状态：进度条 -->
    <div
      v-if="state === 'confirmed' && hasTaskIds && taskStatus < 2"
      class="confirm-progress"
    >
      <el-progress
        :percentage="progressPercent"
        :stroke-width="4"
        :show-text="false"
      />
      <span class="progress-text">{{ doneCount }} / {{ totalCount }}</span>
    </div>

    <!-- 多选项 -->
    <div v-if="options.length > 0 && state === 'idle'" class="confirm-options">
      <div
        v-for="opt in options"
        :key="opt.id"
        class="confirm-option"
        :class="{ selected: selected === opt.id }"
        @click="selected = opt.id"
      >
        <span class="option-radio">
          <span v-if="selected === opt.id" class="radio-dot" />
        </span>
        <span class="option-label">{{ opt.label }}</span>
        <span v-if="opt.description" class="option-desc">{{ opt.description }}</span>
      </div>
    </div>

    <!-- 兜底：无结构化字段时降级渲染 Markdown -->
    <div v-if="!hasStructured" class="msg-text-fallback" v-html="renderMarkdown(card.content || '')" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue"
import { renderMarkdown } from "@/layouts/components/chat/utils"
import type { ConfirmCardData } from "@/api/chat/types"

const props = defineProps<{
  card: ConfirmCardData
}>()

const emit = defineEmits<{
  (e: "confirm", card: ConfirmCardData): void
  (e: "cancel", card: ConfirmCardData): void
  (e: "viewTask", taskId: number): void
}>()

const confirming = ref(false)
const selected = ref<string>(props.card.selected_option || props.card.options?.[0]?.id || "")

const state = computed(() => props.card.state || "idle")
const hasStructured = computed(
  () => !!(props.card.project_name || props.card.suite_name || props.card.suite_names?.length || props.card.task_type || props.card.total != null)
)

// 模块名展示：优先用 suite_names 数组，回退单数 suite_name
const suiteDisplay = computed(() => {
  const names = props.card.suite_names || (props.card.suite_name ? [props.card.suite_name] : [])
  if (!names.length) return ""
  return names.join("、")
})

const SKILL_LABELS: Record<string, string> = {
  core_select: "挑选核心用例",
  case_review: "审核用例质量",
  script_gen: "生成测试脚本",
  case_complete: "完善测试用例",
  case_design: "设计测试用例",
}

const taskLabel = computed(() => {
  const raw = props.card.task_label || props.card.task_type || props.card.skill_name || ""
  return SKILL_LABELS[raw] || raw
})

// 单任务用 task_id；多任务（task_ids.length > 1）返回 null → 跳任务列表
const taskIds = computed(() => props.card.task_ids || (props.card.task_id != null ? [props.card.task_id] : []))
const hasTaskIds = computed(() => taskIds.value.length > 0)
const taskId = computed(() => {
  if (taskIds.value.length === 1) return Number(taskIds.value[0])
  return null
})
const taskStatus = computed(() => (props.card.task_status != null ? Number(props.card.task_status) : 0))

const TASK_STATUS_LABELS: Record<number, string> = {
  0: "排队中",
  1: "执行中",
  2: "已完成",
  3: "失败",
}

const taskStatusLabel = computed(() => TASK_STATUS_LABELS[taskStatus.value] || "排队中")
const taskButtonText = computed(() => {
  const s = taskStatus.value
  if (s === 2) return "查看结果"
  if (s === 3) return "查看详情"
  return "查看任务进度"
})

const options = computed(() => props.card.options || [])
const doneCount = computed(() => Number(props.card.done_count ?? 0))
const totalCount = computed(() => Number(props.card.total_count ?? props.card.total ?? 0))
const progressPercent = computed(() => {
  const total = totalCount.value
  if (total <= 0) return 0
  return Math.min(100, Math.round((doneCount.value / total) * 100))
})

function onConfirm() {
  confirming.value = true
  try {
    emit("confirm", { ...props.card, selected_option: selected.value })
  } finally {
    setTimeout(() => (confirming.value = false), 200)
  }
}

function onCancel() {
  emit("cancel", props.card)
}

function onViewTask() {
  // 单任务传 taskId 跳详情；多任务传 0 → 父组件 onViewTask 跳任务列表
  emit("viewTask", taskId.value ?? 0)
}
</script>

<style scoped>
.confirm-card {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 6px 10px;
  margin-top: 6px;
  transition: opacity 0.2s;
}

.confirm-card.state-confirmed,
.confirm-card.state-cancelled {
  opacity: 0.85;
}

.confirm-card-tag {
  font-size: 11px;
  font-weight: 600;
  color: var(--el-color-primary);
  letter-spacing: 0.3px;
  line-height: 1.4;
  white-space: nowrap;
  flex-shrink: 0;
}

.confirm-card-body {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.confirm-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 7px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 5px;
  font-size: 11px;
  line-height: 1.4;
  white-space: nowrap;
}

.chip-label {
  color: var(--el-text-color-secondary);
  font-size: 10px;
}

.chip-value {
  color: var(--el-text-color-primary);
  font-weight: 500;
}

.confirm-actions-inline {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.confirm-actions-inline :deep(.el-button) {
  height: 24px;
  padding: 0 10px;
  font-size: 11px;
}

.confirm-confirmed-inline {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.confirm-confirmed-inline :deep(.el-button) {
  height: 24px;
  padding: 0 10px;
  font-size: 11px;
}

.task-status-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  line-height: 1.4;
  white-space: nowrap;
}

.task-status-tag.status-0 {
  background: var(--el-color-info-light-9);
  color: var(--el-color-info);
}

.task-status-tag.status-1 {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.task-status-tag.status-2 {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}

.task-status-tag.status-3 {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}

.confirm-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.confirm-progress :deep(.el-progress) {
  flex: 1;
}

.progress-text {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
  white-space: nowrap;
}

.confirm-result-inline {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  flex-shrink: 0;
}

.confirm-result-inline.muted {
  background: var(--el-fill-color);
  color: var(--el-text-color-secondary);
}

.confirm-options {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.confirm-option {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 11px;
}

.confirm-option:hover {
  border-color: var(--el-color-primary-light-5);
}

.confirm-option.selected {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.option-radio {
  width: 12px;
  height: 12px;
  border: 1.5px solid var(--el-border-color);
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.confirm-option.selected .option-radio {
  border-color: var(--el-color-primary);
}

.radio-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--el-color-primary);
}

.option-label {
  font-size: 11px;
  font-weight: 500;
}

.option-desc {
  font-size: 10px;
  color: var(--el-text-color-secondary);
  margin-left: auto;
}

.msg-text-fallback {
  font-size: 12px;
  line-height: 1.55;
  color: var(--el-text-color-primary);
}
</style>
