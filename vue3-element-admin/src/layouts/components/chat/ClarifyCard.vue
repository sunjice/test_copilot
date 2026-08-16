<template>
  <!-- 澄清问答卡片：标题 + 问题列表（text/select）+ 确认/取消 -->
  <div class="clarify-card">
    <div v-if="card.content" class="clarify-title">{{ card.content }}</div>

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
        </el-select>
        <el-input
          v-else
          v-model="answers[q.id]"
          :placeholder="q.placeholder || '请输入'"
          size="small"
          class="clarify-q-input"
        />
      </div>
    </div>

    <div class="clarify-actions">
      <el-button size="small" type="primary" @click="onSubmit">确认</el-button>
      <el-button size="small" plain @click="onCancel">取消</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from "vue"

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
for (const q of questions) answers[q.id] = ""

function onSubmit() {
  emit("submit", props.card.content || "", { ...answers })
}

function onCancel() {
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
</style>
