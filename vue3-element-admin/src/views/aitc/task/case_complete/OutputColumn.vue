<template>
  <div class="text-sm">
    <div v-if="output.fields?.length">
      <div class="text-green-600 text-xs">
        {{ completedCount }} 字段已补全
      </div>
      <div v-if="output.overall_note" class="text-gray-500 text-xs mt-0.5 line-clamp-2">
        {{ output.overall_note }}
      </div>
    </div>
    <div v-else class="text-xs text-gray-400">无补全结果</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"

const props = defineProps<{
  output: Record<string, any>
}>()

const completedCount = computed(() => {
  if (!Array.isArray(props.output.fields)) return 0
  return props.output.fields.filter(
    (f: any) => f.suggested_value !== null && f.suggested_value !== undefined && f.suggested_value !== ""
  ).length
})
</script>
