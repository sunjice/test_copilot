<template>
  <!-- 等待模型响应（还没有任何 segment） -->
  <div v-if="!segments.length" class="streaming waiting-state">
    <span class="waiting-cursor"></span>
    <span class="waiting-text">正在等待模型响应<span class="waiting-dots"><i>.</i><i>.</i><i>.</i></span></span>
  </div>

  <!-- 有 segment 数据后，委托 TurnRenderer 统一渲染 -->
  <div v-else class="streaming turn-state">
    <TurnRenderer :segments="segments" :is-streaming="true" />
  </div>
</template>

<script setup lang="ts">
import TurnRenderer from "./TurnRenderer.vue"
import type { Segment } from "@/api/chat/types"

defineProps<{
  segments: Segment[]
}>()
</script>

<style scoped>
.streaming {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 4px 12px;
}

.waiting-state {
  align-items: center;
  padding: 7px 12px 4px;
}

.turn-state {
  padding: 4px 12px;
}

.waiting-cursor {
  display: inline-block;
  width: 5px;
  height: 14px;
  background: var(--el-color-primary);
  border-radius: 2px;
  animation: waitPulse 0.8s ease-in-out infinite;
}

.waiting-text {
  font-size: 12.5px;
  color: var(--el-text-color-secondary);
  line-height: 1.55;
}

.waiting-dots i {
  font-style: normal;
  animation: dotBlink 1.2s infinite;
}

.waiting-dots i:nth-child(2) { animation-delay: 0.2s; }
.waiting-dots i:nth-child(3) { animation-delay: 0.4s; }

@keyframes dotBlink {
  0%, 100% { opacity: 0.2; }
  50% { opacity: 1; }
}

@keyframes waitPulse {
  0%, 100% { opacity: 0.25; }
  50% { opacity: 1; }
}
</style>
