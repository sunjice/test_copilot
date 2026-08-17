<template>
  <!-- 澄清问答卡片：标题 + 问题列表（text/select，支持自定义输入）+ 确认/取消 -->
  <div class="clarify-card" :class="{ 'clarify-card--done': done }">
    <div v-if="card.content" class="clarify-title">{{ card.content }}</div>

    <!-- 未提交且未取消：显示表单 + 操作按钮 -->
    <template v-if="!done">
      <div v-if="questions.length" class="clarify-questions">
        <div v-for="q in questions" :key="q.id" class="clarify-q">
          <label class="clarify-q-label">
            {{ q.label }}
            <span v-if="q.required" class="clarify-q-required">*</span>
          </label>
          <el-select
            v-if="q.type === 'select' && q.options?.length"
            v-model="answers[q.id]"
            :placeholder="q.placeholder || '请选择'"
            size="small"
            class="clarify-q-input"
          >
            <el-option v-for="opt in q.options" :key="opt.id" :label="opt.label" :value="opt.id" />
            <el-option value="__other__" label="其他（自定义输入）" />
          </el-select>
          <el-input
            v-else
            v-model="answers[q.id]"
            :placeholder="q.placeholder || '请输入'"
            size="small"
            class="clarify-q-input"
          />
          <!-- select 选择"其他"后显示自定义输入框 -->
          <el-input
            v-if="q.type === 'select' && answers[q.id] === '__other__'"
            v-model="customValues[q.id]"
            :placeholder="'请输入自定义的' + q.label"
            size="small"
            class="clarify-q-input clarify-custom-input"
          />
        </div>
      </div>

      <div class="clarify-actions">
        <el-button size="small" type="primary" :loading="submitting" @click="onSubmit">确认</el-button>
        <el-button size="small" plain @click="onCancel">取消</el-button>
      </div>
    </template>

    <!-- 已提交：显示答案汇总 -->
    <div v-else-if="status === 'submitted'" class="clarify-result">
      {{ summary }}
    </div>
    <!-- 已取消：显示取消提示 -->
    <div v-else class="clarify-result clarify-result--cancelled">
      已取消
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from "vue"
import { ElMessage } from "element-plus"

interface Question {
  id: string
  label: string
  type?: "text" | "select"
  placeholder?: string
  options?: Array<{ id: string; label: string }>
  required?: boolean
}

const props = defineProps<{
  card: {
    content?: string
    questions?: Question[]
    [key: string]: any
  }
}>()

const emit = defineEmits<{
  (e: "submit", text: string, answers: Record<string, string>): void
  (e: "cancel"): void
}>()

const questions = (props.card.questions || []) as Question[]
const answers = reactive<Record<string, string>>({})
const customValues = reactive<Record<string, string>>({})
for (const q of questions) {
  answers[q.id] = ""
  customValues[q.id] = ""
}

const submitting = ref(false)

// 卡片状态：优先读 card 里持久化的 clarify_status，本地取消/提交后覆盖
const status = ref<string>(props.card.clarify_status || "")
const done = computed(() => status.value === "submitted" || status.value === "cancelled")

/** 把 question 的答案值转换成用户可读文本 */
function getDisplayAnswer(q: Question, rawValue: string): string {
  if (!rawValue) return "（未填写）"
  if (rawValue === "__other__") {
    return customValues[q.id] || "（自定义）"
  }
  if (q.type === "select") {
    const opt = (q.options || []).find((o) => o.id === rawValue)
    if (opt) return opt.label
  }
  return rawValue
}

/** 已提交时的答案汇总 */
const summary = computed(() => {
  return questions
    .map((q) => `${q.label}：${getDisplayAnswer(q, answers[q.id] || "")}`)
    .join("；")
})

function onSubmit() {
  // 检查必填项
  const missing = questions.filter((q) => {
    if (!q.required) return false
    const val = answers[q.id]
    if (!val) return true
    if (val === "__other__" && !customValues[q.id]) return true
    return false
  })
  if (missing.length > 0) {
    ElMessage.warning(`请填写：${missing.map((q) => q.label).join("、")}`)
    return
  }

  submitting.value = true

  // 把答案组织成可读文本，作为 user 消息发给 LLM
  const lines = questions.map((q) => {
    return `- ${q.label}：${getDisplayAnswer(q, answers[q.id] || "")}`
  })
  const text = "以下是我的回答：\n" + lines.join("\n")

  // __other__ 替换为自定义文本
  const resolved: Record<string, string> = {}
  for (const q of questions) {
    const raw = answers[q.id] || ""
    resolved[q.id] = raw === "__other__" ? (customValues[q.id] || raw) : raw
  }

  status.value = "submitted"
  emit("submit", text, resolved)
}

function onCancel() {
  status.value = "cancelled"
  emit("cancel")
}
</script>

<style scoped>
.clarify-card {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 10px 12px;
  margin-top: 6px;
}

.clarify-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
  line-height: 1.45;
}

.clarify-questions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.clarify-q-label {
  display: block;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.clarify-q-required {
  color: var(--el-color-danger);
  margin-left: 2px;
}

.clarify-q-input {
  width: 100%;
}

.clarify-custom-input {
  margin-top: 4px;
}

.clarify-actions {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.clarify-actions :deep(.el-button) {
  height: 24px;
  padding: 0 10px;
  font-size: 11px;
}

/* 已提交/已取消态：弱化显示 */
.clarify-card--done {
  opacity: 0.75;
}

.clarify-result {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.clarify-result--cancelled {
  color: var(--el-text-color-placeholder);
  font-style: italic;
}
</style>
