<template>
  <div
    class="chat-message"
    :class="[msg.role, { 'has-tools': toolNames.length }]"
    @click="onMsgClick"
  >
    <!-- 用户消息：右侧气泡 -->
    <template v-if="msg.role === 'user'">
      <div class="msg-bubble user-bubble">
        <div class="msg-text">{{ msg.content }}</div>
        <div class="msg-time" :title="fullTime">{{ formatTime(msg.create_time) }}</div>
      </div>
    </template>

    <!-- 系统错误消息 -->
    <template v-else-if="msg.role === 'system' && msg.msg_type === 'error'">
      <div class="msg-error">
        <el-icon class="error-icon"><WarningFilled /></el-icon>
        <span class="error-msg">{{ msg.content }}</span>
        <el-button size="small" type="primary" link @click="$emit('retry')">重试</el-button>
      </div>
    </template>

    <!-- AI 消息：通栏排版，无气泡底色 -->
    <template v-else>
      <div class="msg-content">
        <!-- 文本（完整 Markdown 渲染） -->
        <div v-if="msg.msg_type === 'text'" class="msg-text" v-html="renderedContent" />

        <!-- 操作卡片（核心挑选/审核/脚本生成结果） -->
        <div v-else-if="msg.msg_type === 'action_card'" class="msg-card">
          <div class="msg-text" v-html="renderedContent" />
          <div v-if="msg.metadata_json?.skill_name" class="card-meta">
            技能：{{ msg.metadata_json.skill_name }}
          </div>
          <div v-if="msg.draft_id" class="card-actions">
            <el-button size="small" type="primary" @click="$emit('viewDraft', msg.draft_id!)">
              查看详情
            </el-button>
          </div>
        </div>

        <!-- 草稿卡片 -->
        <div v-else-if="msg.msg_type === 'draft_card'" class="msg-card">
          <div class="msg-text" v-html="renderedContent" />
          <div v-if="msg.metadata_json?.skill_name" class="card-meta">
            草稿类型：{{ msg.metadata_json.skill_name }}
          </div>
          <div v-if="!msg.metadata_json?.draft_status" class="card-actions">
            <el-button size="small" type="primary" @click="$emit('viewDraft', msg.draft_id!)">
              查看草稿
            </el-button>
            <el-button size="small" type="danger" plain @click="$emit('confirmDraft', 'discard')">
              丢弃
            </el-button>
            <el-button size="small" type="success" @click="$emit('confirmDraft', 'confirm')">
              确认采纳
            </el-button>
          </div>
          <div v-else class="card-result" :class="msg.metadata_json.draft_status === 'confirm' ? 'success' : 'muted'">
            {{ msg.metadata_json.draft_status === 'confirm' ? '已采纳' : '已丢弃' }}
          </div>
        </div>

        <!-- 任务卡片 -->
        <div v-else-if="msg.msg_type === 'task_card'" class="msg-card">
          <div class="msg-text" v-html="renderedContent" />
          <div class="card-actions">
            <el-button size="small" type="primary" @click="goTaskDetail">
              {{ taskButtonText }}
            </el-button>
          </div>
        </div>

        <!-- 澄清卡片（LLM 向用户提问收集信息，支持多问题表单） -->
        <div v-else-if="msg.msg_type === 'clarify_card'" class="msg-card">
          <div class="msg-text" v-html="renderedContent" />
          <div class="clarify-form">
            <div
              v-for="(q, idx) in clarifyQuestions"
              :key="q.id"
              class="clarify-field"
              :class="{ 'clarify-field--first': idx === 0 }"
            >
              <label class="clarify-label">
                <span v-if="clarifyQuestions.length > 1" class="clarify-num">{{ idx + 1 }}.</span>
                {{ q.label }}
                <span v-if="q.required" class="clarify-required">*</span>
              </label>
              <el-input
                v-if="q.type === 'text'"
                v-model="clarifyAnswers[q.id]"
                :placeholder="q.placeholder || '请输入'"
                size="small"
              />
              <el-select
                v-else-if="q.type === 'select'"
                v-model="clarifyAnswers[q.id]"
                :placeholder="q.placeholder || '请选择'"
                size="small"
                class="clarify-select"
                popper-class="clarify-popper"
                placement="bottom-start"
                fit-input-width
                :popper-options="{ strategy: 'fixed' }"
              >
                <el-option
                  v-for="opt in (q.options || [])"
                  :key="opt.id"
                  :label="opt.label"
                  :value="opt.id"
                />
                <el-option value="__other__" label="其他（自定义输入）" />
              </el-select>
              <el-input
                v-if="q.type === 'select' && clarifyAnswers[q.id] === '__other__'"
                v-model="clarifyCustomValues[q.id]"
                :placeholder="'请输入自定义的' + q.label"
                size="small"
                class="clarify-custom-input"
              />
            </div>
          </div>
          <div v-if="!clarifySubmitted" class="card-actions">
            <el-button size="small" type="primary" :loading="clarifySubmitting" @click="handleClarifySubmit">
              提交
            </el-button>
          </div>
          <div v-else class="card-result muted">
            {{ clarifyAnswersSummary || '已提交' }}
          </div>
        </div>

        <!-- 确认卡片（任务创建前确认，支持多选项） -->
        <div v-else-if="msg.msg_type === 'confirm_card'" class="msg-card">
          <div class="msg-text" v-html="renderedContent" />

          <!-- 多选项（如审核范围选择） -->
          <div v-if="confirmOptions.length > 0 && confirmState === 'idle'" class="confirm-options">
            <div
              v-for="opt in confirmOptions"
              :key="opt.id"
              class="confirm-option"
              :class="{ selected: selectedOptionId === opt.id }"
              @click="selectedOptionId = opt.id"
            >
              <span class="option-radio">
                <span v-if="selectedOptionId === opt.id" class="radio-dot" />
              </span>
              <span class="option-label">{{ opt.label }}</span>
              <span v-if="opt.description" class="option-desc">{{ opt.description }}</span>
            </div>
          </div>

          <div v-if="confirmState === 'idle'" class="card-actions">
            <el-button size="small" type="primary" :loading="confirming" @click="handleConfirm">
              确认创建
            </el-button>
            <el-button size="small" plain @click="handleCancel">
              取消
            </el-button>
          </div>
          <div v-else-if="confirmState === 'confirmed'" class="card-result success">
            任务已创建
          </div>
          <div v-else class="card-result muted">
            已取消
          </div>
        </div>

        <!-- 其他类型直接渲染文本 -->
        <div v-else class="msg-text" v-html="renderedContent" />

        <!-- Agent 工具调用记录：可折叠思考过程 -->
        <div v-if="hasToolActivity" class="msg-tool-steps">
          <details class="tool-details">
            <summary class="tool-summary">
              <el-icon><Tools /></el-icon>
              <span>思考过程（{{ toolCalls }} 个步骤）</span>
            </summary>
            <!-- 有工具名称列表：按名称展示 -->
            <div v-if="toolNames.length" class="tool-list">
              <div v-for="(name, i) in toolNames" :key="i" class="tool-item">
                <span class="tool-step-idx">{{ i + 1 }}.</span>
                <el-icon class="tool-check"><Check /></el-icon>
                <span>{{ name }}</span>
              </div>
            </div>
            <!-- 无工具名称但 tool_calls > 0 的兜底列表 -->
            <div v-else class="tool-list">
              <div v-for="i in toolCalls" :key="i" class="tool-item">
                <span class="tool-step-idx">{{ i }}.</span>
                <el-icon class="tool-check"><Check /></el-icon>
                <span>工具调用</span>
              </div>
            </div>
          </details>
        </div>

        <div class="msg-time" :title="fullTime">{{ formatTime(msg.create_time) }}</div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { ElMessage } from "element-plus"
import { Check, Tools, WarningFilled } from "@element-plus/icons-vue"
import { renderMarkdown, formatTimeHM, setupCodeCopy, exportTableToExcel } from "./utils"
import type { ChatMessage } from "@/api/chat/types"

const props = defineProps<{
  msg: ChatMessage
}>()

const emit = defineEmits<{
  viewDraft: [id: number]
  confirmDraft: [action: string]
  confirmTask: [metadata: Record<string, any>]
  cancelTask: [metadata: Record<string, any>]
  submitClarify: [text: string, answers: Record<string, string>]
  retry: []
}>()

const router = useRouter()
const confirming = ref(false)
const msgEl = ref<HTMLElement>()

// ── 澄清卡片（clarify_card）逻辑 ──

interface ClarifyQuestion {
  id: string
  label: string
  type: string
  placeholder: string
  options: { id: string; label: string }[]
  required: boolean
}

const clarifyQuestions = computed<ClarifyQuestion[]>(() => {
  return props.msg.metadata_json?.questions || []
})

const clarifyAnswers = ref<Record<string, string>>({})
const clarifyCustomValues = ref<Record<string, string>>({})
const clarifySubmitting = ref(false)

/** 是否已提交：优先从 metadata 中读取（历史消息恢复），其次用本地 ref */
const clarifySubmitted = computed(() => {
  return props.msg.metadata_json?.clarify_status === "submitted"
})

/** 已提交时显示的答案汇总 */
const clarifyAnswersSummary = computed(() => {
  const saved = props.msg.metadata_json?.clarify_answers as Record<string, string> | undefined
  if (!saved || !clarifyQuestions.value.length) return ""
  return clarifyQuestions.value
    .map((q) => `${q.label}：${getDisplayAnswer(q, saved[q.id] || "")}`)
    .join("；")
})

/** 把 question 的答案值转换成用户可读的文本 */
function getDisplayAnswer(q: ClarifyQuestion, rawValue: string): string {
  if (!rawValue) return "（未填写）"
  if (rawValue === '__other__') {
    return clarifyCustomValues.value[q.id] || "（自定义）"
  }
  if (q.type === 'select') {
    const opt = (q.options || []).find(o => o.id === rawValue)
    if (opt) return opt.label
  }
  return rawValue
}

function handleClarifySubmit() {
  const qs = clarifyQuestions.value
  const answers = clarifyAnswers.value
  const customs = clarifyCustomValues.value

  // 检查必填项
  const missing = qs.filter(q => {
    if (!q.required) return false
    const val = answers[q.id]
    if (!val) return true
    if (val === '__other__' && !customs[q.id]) return true
    return false
  })
  if (missing.length > 0) {
    ElMessage.warning(`请填写：${missing.map(q => q.label).join("、")}`)
    return
  }

  clarifySubmitting.value = true
  const lines = qs.map((q) => {
    const a = getDisplayAnswer(q, answers[q.id] || "")
    return `- ${q.label}：${a}`
  })
  const text = "以下是我的回答：\n" + lines.join("\n")

  // 提交给后端时，__other__ 替换为自定义文本
  const resolved: Record<string, string> = {}
  for (const q of qs) {
    const raw = answers[q.id] || ''
    resolved[q.id] = raw === '__other__' ? (customs[q.id] || raw) : raw
  }
  emit("submitClarify", text, resolved)
}

/** 确认卡片中的多选项（如审核范围选择） */
interface ConfirmOption {
  id: string
  label: string
  description?: string
}

const selectedOptionId = ref("")

/** 初始化时从持久化的 _selected_option 恢复选中项 */
function initSelectedOption() {
  const saved = props.msg.metadata_json?._selected_option as string | undefined
  if (saved) selectedOptionId.value = saved
}
initSelectedOption()

const confirmOptions = computed<ConfirmOption[]>(() => {
  const raw = props.msg.metadata_json?.options
  if (Array.isArray(raw) && raw.length > 0) {
    if (!selectedOptionId.value) {
      selectedOptionId.value = raw[0]?.id || ""
    }
    return raw
  }
  return []
})
const confirmState = computed<'idle' | 'confirmed' | 'cancelled'>(() => {
  const status = props.msg.metadata_json?.confirm_status
  if (status === 'confirmed') return 'confirmed'
  if (status === 'cancelled') return 'cancelled'
  return 'idle'
})

async function handleConfirm() {
  confirming.value = true
  try {
    const meta = { ...(props.msg.metadata_json || {}) }
    if (selectedOptionId.value) {
      meta._selected_option = selectedOptionId.value
    }
    emit('confirmTask', meta)
  } finally {
    confirming.value = false
  }
}

function handleCancel() {
  emit('cancelTask', props.msg.metadata_json || {})
}

const taskButtonText = computed(() => {
  const status = props.msg.metadata_json?.task_status
  if (status === 2) return "查看审核结果"
  if (status === 3) return "查看详情"
  return "查看任务进度"
})

function goTaskDetail() {
  const taskId = props.msg.metadata_json?.task_id
  if (taskId) {
    router.push(`/aitc/tasks/${taskId}`)
  } else {
    router.push("/aitc/tasks")
  }
}

// 完整 Markdown 渲染
const renderedContent = computed(() => renderMarkdown(props.msg.content || ""))

const TOOL_LABELS = new Map<string, string>([
  ["list_projects", "列出项目"],
  ["get_suite_tree", "查看模块树"],
  ["search_cases", "搜索用例"],
  ["get_case_detail", "查看用例详情"],
  ["get_suite_samples", "查看样本用例"],
  ["ask_question", "询问用户"],
  ["create_core_select_task", "创建核心挑选任务"],
  ["create_case_review_task", "创建审核任务"],
  ["create_script_gen_task", "创建脚本生成任务"],
  ["complete_case_steps", "补写测试步骤"],
  ["create_case_complete_task", "完善用例"],
  ["design_test_case", "设计测试用例"],
])

/** 已调用的 Agent 工具名称列表（按调用顺序，不去重，过滤空值） */
const toolNames = computed(() => {
  const raw = props.msg.metadata_json?.tool_names
  if (!Array.isArray(raw) || raw.length === 0) return []
  return raw
    .filter((n: string) => !!n)
    .map((n: string) => TOOL_LABELS.get(n) || n)
})

/** 工具调用次数：优先用 tool_names 长度，兜底用 metadata.tool_calls */
const toolCalls = computed(() => {
  if (toolNames.value.length > 0) return toolNames.value.length
  return props.msg.metadata_json?.tool_calls ?? 0
})

/** 有工具调用记录（含无名称仅次数的兜底场景） */
const hasToolActivity = computed(() =>
  toolNames.value.length > 0 ||
  (props.msg.metadata_json?.tool_calls ?? 0) > 0
)

function formatTime(time: string | null) {
  return formatTimeHM(time)
}

const fullTime = computed(() => {
  if (!props.msg.create_time) return ""
  const d = new Date(props.msg.create_time)
  return d.toLocaleString("zh-CN")
})

// 事件委托：代码块复制 / 表格下载
function onMsgClick(e: MouseEvent) {
  // 表格下载按钮
  const downloadBtn = (e.target as HTMLElement).closest(".md-table-download") as HTMLElement | null
  if (downloadBtn) {
    const wrapper = downloadBtn.closest(".md-table-wrapper") as HTMLElement | null
    if (wrapper) {
      const table = wrapper.querySelector("table") as HTMLTableElement | null
      if (table) {
        exportTableToExcel(table).catch((err) => {
          console.error("导出表格失败:", err)
        })
        return
      }
    }
  }

  // 代码块复制按钮
  const btn = (e.target as HTMLElement).closest(".md-code-copy") as HTMLElement | null
  if (!btn) return
  const code = btn.getAttribute("data-code")
  if (!code) return
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = "已复制"
    setTimeout(() => {
      btn.textContent = "复制"
    }, 2000)
  })
}
</script>

<style scoped>
/* ── 消息行 ── */
.chat-message {
  display: flex;
  gap: 6px;
  padding: 5px 12px;
  margin-bottom: 0;
  transition: background 0.15s;
}

.chat-message.user {
  justify-content: flex-end;
}

/* ── 用户气泡 ── */
.msg-bubble {
  position: relative;
  max-width: 78%;
  padding: 5px 10px 16px;
  border-radius: 12px;
  line-height: 1.45;
  font-size: 12.5px;
  word-break: break-word;
}

.user-bubble {
  background: var(--el-color-primary-light-8);
  color: var(--el-text-color-primary);
  border: 1px solid var(--el-color-primary-light-5);
}

/* ── AI 消息内容区（通栏，无背景） ── */
.msg-content {
  flex: 1;
  min-width: 0;
  position: relative;
  padding-bottom: 2px;
}

.msg-text {
  line-height: 1.55;
  font-size: 12.5px;
  color: var(--el-text-color-primary);
  word-break: break-word;
}

/* Markdown 渲染元素样式（紧凑排版） */
.msg-text :deep(p) {
  margin: 0 0 4px;
}
.msg-text :deep(p:last-child) {
  margin-bottom: 0;
}
.msg-text :deep(ul),
.msg-text :deep(ol) {
  padding-left: 16px;
  margin: 2px 0 4px;
}
.msg-text :deep(li) {
  margin-bottom: 1px;
}
.msg-text :deep(h1),
.msg-text :deep(h2),
.msg-text :deep(h3),
.msg-text :deep(h4) {
  margin: 6px 0 3px;
  font-weight: 600;
  line-height: 1.3;
}
.msg-text :deep(h1) { font-size: 15px; }
.msg-text :deep(h2) { font-size: 14px; }
.msg-text :deep(h3) { font-size: 13px; }
.msg-text :deep(h4) { font-size: 12.5px; }
.msg-text :deep(blockquote) {
  margin: 3px 0;
  padding: 2px 10px;
  border-left: 3px solid var(--el-color-primary-light-5);
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  border-radius: 0 6px 6px 0;
}
.msg-text :deep(table) {
  border-collapse: collapse;
  margin: 0;
  width: 100%;
  font-size: 11.5px;
}
.msg-text :deep(th),
.msg-text :deep(td) {
  border: 1px solid var(--el-border-color-lighter);
  padding: 2px 7px;
  text-align: left;
}
.msg-text :deep(th) {
  background: var(--el-fill-color-light);
  font-weight: 600;
}

/* ── 表格下载工具栏 ── */
.msg-text :deep(.md-table-wrapper) {
  margin: 6px 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow: hidden;
}

.msg-text :deep(.md-table-toolbar) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 8px;
  background: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.msg-text :deep(.md-table-label) {
  font-size: 10px;
  color: var(--el-text-color-secondary);
}

.msg-text :deep(.md-table-download) {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 8px;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 4px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 10px;
  cursor: pointer;
  transition: all 0.15s;
}

.msg-text :deep(.md-table-download:hover) {
  background: var(--el-color-primary-light-7);
  border-color: var(--el-color-primary);
}
.msg-text :deep(a) {
  color: var(--el-color-primary);
  text-decoration: underline;
}
.msg-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--el-border-color-lighter);
  margin: 5px 0;
}
.msg-text :deep(strong) {
  font-weight: 500;
  color: var(--el-text-color-primary);
}
.msg-text :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 0 3px;
  border-radius: 3px;
  font-size: 11px;
  font-family: "SF Mono", "Fira Code", Consolas, monospace;
}

.user-bubble .msg-text :deep(code) {
  background: rgba(0, 0, 0, 0.1);
}

/* ── 代码块 ── */
.msg-content :deep(.md-code-block) {
  background: #1e1e2e;
  border-radius: 6px;
  margin: 3px 0;
  overflow: hidden;
}

.msg-content :deep(.md-code-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 10px;
  background: rgba(255, 255, 255, 0.06);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.msg-content :deep(.md-code-lang) {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.55);
  text-transform: uppercase;
}

.msg-content :deep(.md-code-copy) {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.65);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  cursor: pointer;
  transition: all 0.15s;
}

.msg-content :deep(.md-code-copy:hover) {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.msg-content :deep(.hljs) {
  display: block;
  padding: 7px 10px;
  overflow-x: auto;
  font-size: 11px;
  line-height: 1.45;
  font-family: "SF Mono", "Fira Code", Consolas, monospace;
  color: #cdd6f4;
}

/* highlight.js 主题基础样式 (Catppuccin Mocha) */
.msg-content :deep(.hljs-keyword) { color: #cba6f7; }
.msg-content :deep(.hljs-string) { color: #a6e3a1; }
.msg-content :deep(.hljs-number) { color: #fab387; }
.msg-content :deep(.hljs-comment) { color: #6c7086; font-style: italic; }
.msg-content :deep(.hljs-function) { color: #89b4fa; }
.msg-content :deep(.hljs-title) { color: #89b4fa; }
.msg-content :deep(.hljs-type) { color: #f9e2af; }
.msg-content :deep(.hljs-literal) { color: #fab387; }
.msg-content :deep(.hljs-built_in) { color: #f38ba8; }
.msg-content :deep(.hljs-attr) { color: #89b4fa; }
.msg-content :deep(.hljs-params) { color: #f2cdcd; }
.msg-content :deep(.hljs-meta) { color: #f5c2e7; }
.msg-content :deep(.hljs-property) { color: #89b4fa; }
.msg-content :deep(.hljs-variable) { color: #f38ba8; }
.msg-content :deep(.hljs-selector-class) { color: #a6e3a1; }
.msg-content :deep(.hljs-punctuation) { color: #bac2de; }
.msg-content :deep(.hljs-operator) { color: #89dceb; }
.msg-content :deep(.hljs-regexp) { color: #f38ba8; }

/* ── 工具调用：可折叠思考过程 ── */
.msg-tool-steps {
  margin-top: 3px;
}

.tool-details {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow: hidden;
}

.tool-summary {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  user-select: none;
  background: var(--el-fill-color-lighter);
  transition: background 0.15s;
}

.tool-summary:hover {
  background: var(--el-fill-color-light);
}

.tool-summary .el-icon {
  font-size: 12px;
  color: var(--el-color-primary);
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 2px 8px 3px 20px;
}

.tool-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}

.tool-step-idx {
  font-size: 10px;
  color: var(--el-text-color-placeholder);
  min-width: 14px;
  flex-shrink: 0;
}

.tool-check {
  font-size: 11px;
  color: var(--el-color-success);
  flex-shrink: 0;
}

/* ── 卡片样式 ── */
.msg-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}

.card-meta {
  font-size: 10px;
  color: var(--el-text-color-secondary);
  padding-top: 2px;
  border-top: 1px dashed var(--el-border-color-lighter);
}

.card-actions {
  display: flex;
  gap: 4px;
  padding-top: 2px;
}

.card-result {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 4px;
  margin-top: 2px;
}

.card-result.success {
  color: var(--el-color-success);
  background: var(--el-color-success-light-9);
}

.card-result.muted {
  color: var(--el-text-color-placeholder);
  background: var(--el-fill-color);
}

/* confirm_card 多选项 */
.confirm-options {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0;
}

.confirm-option {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
  cursor: pointer;
  transition: all 0.15s;
  font-size: 12px;
}

.confirm-option:hover {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}

.confirm-option.selected {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.option-radio {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid var(--el-border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: border-color 0.15s;
}

.confirm-option.selected .option-radio {
  border-color: var(--el-color-primary);
}

.radio-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-color-primary);
}

.option-label {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.option-desc {
  color: var(--el-text-color-secondary);
  font-size: 11px;
}

/* clarify_card 问答表单 */
.clarify-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 2px 0;
}

.clarify-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* 多问题间的分隔线 */
.clarify-field:not(.clarify-field--first) {
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
}

.clarify-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.clarify-num {
  display: inline-block;
  color: var(--el-color-primary);
  font-weight: 600;
  min-width: 16px;
  margin-right: 2px;
}

.clarify-required {
  color: var(--el-color-danger);
  margin-left: 1px;
}

.clarify-select {
  width: 100%;
}

.clarify-custom-input {
  margin-top: 4px;
}

/* ── 时间戳（悬停显示详细时间） ── */
.msg-time {
  position: absolute;
  bottom: 4px;
  right: 10px;
  font-size: 9px;
  color: var(--el-text-color-placeholder);
  line-height: 1;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s;
}

.user-bubble .msg-time {
  right: 10px;
}

.msg-content .msg-time {
  position: relative;
  right: auto;
  bottom: auto;
  display: inline-block;
  margin-top: 2px;
}

.chat-message:hover .msg-time {
  opacity: 1;
}

/* ── 错误消息 ── */
.msg-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--el-color-danger-light-5);
  background: var(--el-color-danger-light-9);
  font-size: 12px;
  line-height: 1.45;
  flex: 1;
}

.error-icon {
  font-size: 16px;
  color: var(--el-color-danger);
  flex-shrink: 0;
}

.error-msg {
  flex: 1;
  color: var(--el-text-color-primary);
}

/* ── 消息操作栏（悬停显示） ── */
.msg-actions {
  display: flex;
  gap: 0;
  opacity: 0;
  transition: opacity 0.2s;
  margin-top: 2px;
}

.chat-message:hover .msg-actions {
  opacity: 1;
}
</style>

<!-- 全局样式：clarify popper 下拉选项缩小到聊天主体尺寸 -->
<style>
.clarify-popper {
  --el-font-size-base: 12px;
}

.clarify-popper .el-select-dropdown__item {
  font-size: 12px;
  line-height: 1.4;
  padding: 4px 10px;
  margin: 1px 4px;
  border-radius: 4px;
  height: auto !important;
  min-height: unset !important;
}
</style>
