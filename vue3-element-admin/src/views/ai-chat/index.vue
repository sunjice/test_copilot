<template>
  <div class="ai-chat-page">
    <!-- 纯对话形态（kb 域）：无工作区树 -->
    <ChatPanel ref="chatPanelRef" />
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted, onActivated, onDeactivated, nextTick } from "vue"
import ChatPanel from "./chat/ChatPanel.vue"
import { useAiContextStore } from "@/stores/aiContext"

const aiContextStore = useAiContextStore()
const chatPanelRef = ref<InstanceType<typeof ChatPanel> | null>(null)

// kb 域独立页：注册到 kb 域上下文桶
aiContextStore.register("kb", "kb")

// keep-alive 场景：切走时保存滚动位置，切回时恢复（保留用户停留的位置）
onDeactivated(() => {
  chatPanelRef.value?.saveScrollPosition()
})
onActivated(() => {
  nextTick(() => {
    chatPanelRef.value?.restoreScrollPosition()
  })
})

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

.ai-chat-page > :deep(.ai-chat-panel) {
  flex: 1;
  min-width: 0;
}
</style>
