<template>
  <!--
    合并的多张 confirm_card 渲染：
    - 同一条 AI 消息气泡
    - 思考 / 工具调用原文（TurnRenderer）在上方
    - 每张卡片横排紧凑展示（项目 / 模块 / 任务类型 / 用例数量 + 确认/取消按钮同行右侧）
    - 整体高度压扁，与普通消息气泡保持接近
  -->
  <div class="chat-message assistant">
    <div class="message-avatar">
      <div class="avatar-box">AI</div>
    </div>
    <div class="message-main">
      <!-- 思考 + 工具调用原文（多卡片共享，取首条 segments） -->
      <TurnRenderer
        v-if="firstSegments.length"
        :segments="firstSegments"
      />

      <!-- 多张 confirm_card：紧凑横排 -->
      <div
        v-for="(msg, idx) in messages"
        :key="msg.id || idx"
        class="confirm-card"
        :class="[`state-${confirmStateOf(msg)}`]"
      >
        <div class="confirm-card-body">
          <!-- 左侧：信息 chip 横排（前面带"创建任务："提示） -->
          <div v-if="hasStructuredMeta(msg)" class="confirm-chips">
            <span class="confirm-card-tag">创建任务：</span>
            <span v-if="metaOf(msg).project_name" class="chip">
              <span class="chip-label">项目</span>
              <span class="chip-value">{{ metaOf(msg).project_name }}</span>
            </span>
            <span v-if="metaOf(msg).suite_name" class="chip">
              <span class="chip-label">模块</span>
              <span class="chip-value">{{ metaOf(msg).suite_name }}</span>
            </span>
            <span v-if="taskLabelOf(msg)" class="chip">
              <span class="chip-label">任务类型</span>
              <span class="chip-value">{{ taskLabelOf(msg) }}</span>
            </span>
            <span v-if="metaOf(msg).total != null" class="chip">
              <span class="chip-label">用例数量</span>
              <span class="chip-value">{{ metaOf(msg).total }} 条</span>
            </span>
          </div>

          <!-- 右侧：确认/取消 按钮（同行） -->
          <div v-if="confirmStateOf(msg) === 'idle'" class="confirm-actions-inline">
            <el-button
              size="small"
              type="primary"
              :loading="loadingMap[msg.id ?? idx]"
              @click="onConfirm(msg, idx)"
            >
              确认
            </el-button>
            <el-button size="small" plain @click="onCancel(msg)">取消</el-button>
          </div>
          <div v-else-if="confirmStateOf(msg) === 'confirmed'" class="confirm-result-inline success">
            任务已创建
          </div>
          <div v-else class="confirm-result-inline muted">已取消</div>
        </div>

        <!-- 多选项（审核范围选择等）单独占一行 -->
        <div
          v-if="getOptions(msg).length > 0 && confirmStateOf(msg) === 'idle'"
          class="confirm-options"
        >
          <div
            v-for="opt in getOptions(msg)"
            :key="opt.id"
            class="confirm-option"
            :class="{ selected: selectedOf(msg) === opt.id }"
            @click="selectOption(msg, opt.id)"
          >
            <span class="option-radio">
              <span v-if="selectedOf(msg) === opt.id" class="radio-dot" />
            </span>
            <span class="option-label">{{ opt.label }}</span>
            <span v-if="opt.description" class="option-desc">{{ opt.description }}</span>
          </div>
        </div>

        <!-- 兜底：如果后端没给结构化字段，降级渲染 Markdown -->
        <div v-if="!hasStructuredMeta(msg)" class="msg-text-fallback" v-html="renderMarkdown(msg.content || '')" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed } from "vue"
import { renderMarkdown } from "@/layouts/components/chat/utils"
import TurnRenderer from "@/layouts/components/chat/TurnRenderer.vue"
import type { ChatMessage, Segment } from "@/api/chat/types"

const props = defineProps<{
  messages: ChatMessage[]
}>()

const emit = defineEmits<{
  (e: "confirmTask", msg: ChatMessage, meta: Record<string, any>): void
  (e: "cancelTask", msg: ChatMessage, meta: Record<string, any>): void
}>()

const loadingMap = reactive<Record<string | number, boolean>>({})

/** 首条卡片的 segments（多卡时各卡 metadata.segments 相同，用首条渲染 TurnRenderer） */
const firstSegments = computed<Segment[]>(() => {
  const first = props.messages[0]
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const segs = (first?.metadata_json as any)?.segments
  return Array.isArray(segs) ? (segs as Segment[]) : []
})

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function metaOf(msg: ChatMessage): Record<string, any> {
  return (msg.metadata_json as Record<string, any>) || {}
}

function hasStructuredMeta(msg: ChatMessage): boolean {
  const m = metaOf(msg)
  return !!(m.project_name || m.suite_name || m.task_type || m.total != null)
}

function taskLabelOf(msg: ChatMessage): string {
  const m = metaOf(msg)
  const raw = m.task_label || m.task_type || m.skill_name || ""
  return SKILL_LABELS[raw] || raw
}

/**
 * 技能命令 → 中文标签（优先使用后端的 task_label，否则按 skill_name 映射）
 * 与 LayoutChat/ChatPanel 的 SKILL_LABELS 保持一致
 */
const SKILL_LABELS: Record<string, string> = {
  core_select: "挑选核心用例",
  case_review: "审核用例质量",
  script_gen: "生成测试脚本",
  case_complete: "完善测试用例",
  case_design: "设计测试用例",
}

interface Option { id: string; label: string; description?: string }
function getOptions(msg: ChatMessage): Option[] {
  const raw = metaOf(msg).options
  return Array.isArray(raw) ? raw : []
}

const selectedMap = reactive<Record<string | number, string>>({})

function selectedOf(msg: ChatMessage): string {
  const k = msg.id ?? msg.create_time ?? Math.random()
  const saved = metaOf(msg)._selected_option as string | undefined
  if (saved) return saved
  return selectedMap[k as any] || getOptions(msg)[0]?.id || ""
}

function selectOption(msg: ChatMessage, id: string) {
  const k = msg.id ?? msg.create_time ?? Math.random()
  selectedMap[k as any] = id
}

function confirmStateOf(msg: ChatMessage): "idle" | "confirmed" | "cancelled" {
  const s = metaOf(msg).confirm_status
  if (s === "confirmed") return "confirmed"
  if (s === "cancelled") return "cancelled"
  return "idle"
}

function onConfirm(msg: ChatMessage, idx: number) {
  const k = msg.id ?? idx
  loadingMap[k] = true
  const meta = { ...metaOf(msg) }
  const sel = selectedOf(msg)
  if (sel) meta._selected_option = sel
  try {
    emit("confirmTask", msg, meta)
  } finally {
    setTimeout(() => (loadingMap[k] = false), 200)
  }
}

function onCancel(msg: ChatMessage) {
  emit("cancelTask", msg, metaOf(msg))
}
</script>

<style scoped>
.chat-message.assistant {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

.message-avatar {
  flex-shrink: 0;
}

.avatar-box {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff, #1677ff);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.message-main {
  flex: 1;
  min-width: 0;
}

.confirm-card {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 6px 10px;
  margin-top: 6px;
  transition: opacity 0.2s;
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

.confirm-card.state-confirmed,
.confirm-card.state-cancelled {
  opacity: 0.65;
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

.confirm-result-inline {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  flex-shrink: 0;
}

.confirm-result-inline.success {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success-dark-2);
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
