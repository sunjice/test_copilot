<template>
  <div class="ai-chat-panel">
    <div ref="chatContainerRef" class="chat-messages">
      <template v-for="msg in messages" :key="msg.id">
        <div v-if="msg.role === 'user'" class="message-time-divider">
          {{ formatHistoryTime(msg.create_time) }}
        </div>
        <ChatMessage
          :msg="msg"
          @confirm-create-task="handleConfirmTask"
          @cancel-task="handleCancelTask"
          @submit-clarify="handleClarifySubmit"
          @retry="retryLastMessage"
        />
      </template>

      <div v-if="streaming" class="streaming-indicator">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>AI 思考中...</span>
      </div>
    </div>

    <div class="chat-input-area">
      <div class="input-wrapper">
        <el-input
          v-model="input"
          type="textarea"
          :rows="3"
          placeholder="输入 / 选择快捷指令，输入 @ 引用上下文，Shift+Enter 换行，Enter 发送"
          resize="none"
          @keydown="handleKeydown"
        />
        <div class="input-actions">
          <el-button v-if="streaming" type="danger" size="small" @click="stopGeneration">
            <el-icon><VideoPause /></el-icon>
            停止
          </el-button>
          <el-button v-else type="primary" size="small" :loading="loading" @click="handleSend">
            <el-icon><Promotion /></el-icon>
            发送
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from "vue"
import ChatMessage from "@/layouts/components/chat/ChatMessage.vue"
import { useChat } from "@/layouts/components/chat/useChat"
import { formatHistoryTime } from "@/layouts/components/chat/utils"

const props = defineProps<{
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  context: Record<string, any>
}>()

const chatContainerRef = ref<HTMLElement>()
const input = ref("")

const {
  messages,
  loading,
  streaming,
  pageContext,
  sendMessage,
  stopGeneration,
  retryLastMessage,
  confirmCreateTask,
  cancelTask,
  submitClarifyAnswers,
  init,
} = useChat()

onMounted(() => {
  init()
})

// 父组件传入的上下文（工作区选择结果）→ 同步到 useChat 的 pageContext
// sendMessage 建会话 / 发消息时会把 pageContext 注入后端
watch(
  () => props.context,
  (ctx) => {
    if (ctx && Object.keys(ctx).length > 0) {
      pageContext.value = { ...ctx }
    }
  },
  { deep: true, immediate: true }
)

watch(
  () => messages.value.length,
  () => {
    nextTick(() => scrollToBottom())
  }
)

function scrollToBottom() {
  const el = chatContainerRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

async function handleSend() {
  const text = input.value.trim()
  if (!text || loading.value) return
  await sendMessage(text)
  input.value = ""
  scrollToBottom()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function handleConfirmTask(metadata: Record<string, any>) {
  confirmCreateTask(metadata)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function handleCancelTask(metadata: Record<string, any>) {
  cancelTask(metadata)
}

function handleClarifySubmit(_text: string, answers: Record<string, string>) {
  submitClarifyAnswers(answers)
}
</script>

<style scoped lang="scss">
.ai-chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message-time-divider {
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin: 16px 0;
}

.streaming-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  padding: 12px 0;
}

.chat-input-area {
  border-top: 1px solid var(--el-border-color-light);
  padding: 12px 20px 20px;
}

.input-wrapper {
  position: relative;

  :deep(.el-textarea__inner) {
    padding-bottom: 40px;
  }
}

.input-actions {
  position: absolute;
  right: 12px;
  bottom: 12px;
  display: flex;
  gap: 8px;
}
</style>
