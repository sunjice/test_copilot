<template>
  <div class="ai-trace-page">
    <!-- 左：会话 + 轮次列表 -->
    <el-card class="left-panel" shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-semibold">会话列表</span>
          <el-button size="small" text type="primary" @click="loadSessions">刷新</el-button>
        </div>
      </template>

      <el-select
        v-model="activeSessionId"
        placeholder="选择会话"
        clearable
        filterable
        class="w-full mb-3"
        @change="handleSessionChange"
      >
        <el-option
          v-for="s in sessions"
          :key="s.session_id"
          :label="`会话 #${s.session_id}（${s.log_count} 条事件）`"
          :value="s.session_id"
        />
      </el-select>

      <div v-loading="roundsLoading" class="round-list">
        <div
          v-for="r in rounds"
          :key="r.message_id"
          class="round-item"
          :class="{ active: r.message_id === activeMessageId }"
          @click="selectRound(r.message_id)"
        >
          <div class="flex items-center justify-between">
            <span class="round-id">轮 #{{ r.message_id }}</span>
            <span class="round-count">{{ r.count }} 次调用</span>
          </div>
          <div class="round-time">{{ r.time }}</div>
          <div class="round-actions">{{ r.actions }}</div>
        </div>
        <el-empty v-if="!roundsLoading && rounds.length === 0" description="暂无轨迹" :image-size="60" />
      </div>
    </el-card>

    <!-- 右：轨迹详情 -->
    <div class="right-panel">
      <!-- 用量汇总（紧凑单行） -->
      <div v-if="usage" class="usage-bar">
        <span class="usage-title">轮 #{{ activeMessageId }}</span>
        <span class="usage-cell">
          <em>输入</em>{{ fmtNum(usage.prompt_tokens) }}
          <i>命中 {{ fmtNum(usage.prompt_cache_hit_tokens) }} · 未命中 {{ fmtNum(usage.prompt_cache_miss_tokens) }} · 写入 {{ fmtNum(usage.prompt_cache_write_tokens) }}</i>
        </span>
        <span class="usage-cell">
          <em>输出</em>{{ fmtNum(usage.completion_tokens) }}
          <i>思考 {{ fmtNum(usage.reasoning_tokens) }} · 回复 {{ fmtNum(usage.reply_tokens) }}</i>
        </span>
        <span class="usage-cell">
          <em>缓存命中率</em>{{ (usage.cache_hit_rate * 100).toFixed(1) }}%
          <i>{{ usage.request_count }} 次调用</i>
        </span>
      </div>

      <!-- 调用链 -->
      <el-card class="trace-card" shadow="never">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-semibold">调用链（seq 平铺）</span>
            <el-button size="small" text type="primary" @click="copyTrace">复制 JSON</el-button>
          </div>
        </template>

        <div v-loading="traceLoading">
          <div v-if="trace.length === 0 && !traceLoading" class="py-8 text-center text-gray-400">
            选择左侧轮次查看调用链
          </div>
          <div v-else class="trace-list">
            <div
              v-for="ev in trace"
              :key="ev.id"
              class="trace-node"
              :class="`status-${ev.status}`"
            >
              <div class="node-head">
                <el-tag :type="eventTypeTag(ev.event_type)" size="small" class="mr-2">
                  {{ ev.event_type }}
                </el-tag>
                <el-tag size="small" type="info" class="mr-2">{{ ev.action }}</el-tag>
                <el-tag :type="statusTag(ev.status)" size="small" class="mr-2">
                  {{ ev.status === "success" ? "成功" : ev.status }}
                </el-tag>
                <span class="text-xs text-gray-400 mr-2">{{ ev.model }}</span>
                <span class="text-xs text-gray-400">{{ ev.duration_ms }}ms</span>
                <span class="ml-auto text-xs text-gray-400">seq={{ ev.seq }}</span>
              </div>

              <div class="node-meta">
                <span class="meta-item">provider: {{ ev.provider || "-" }}</span>
                <span class="meta-item" :title="ev.api_base">api: {{ ev.api_base || "-" }}</span>
                <span class="meta-item">
                  tokens: {{ ev.prompt_tokens }} + {{ ev.completion_tokens }}
                  <template v-if="ev.reasoning_tokens">(思考 {{ ev.reasoning_tokens }})</template>
                </span>
                <span class="meta-item">cache: 命中 {{ ev.prompt_cache_hit_tokens }} / 未命中 {{ ev.prompt_cache_miss_tokens }}</span>
                <span class="meta-item">{{ ev.create_time }}</span>
              </div>

              <div v-if="ev.error_msg" class="node-error">{{ ev.error_msg }}</div>

              <!-- 展开详情 -->
              <el-collapse-transition>
                <div v-if="expandedId === ev.id" class="node-detail">
                  <el-tabs v-model="detailTab">
                    <el-tab-pane label="请求 messages" name="req">
                      <pre class="json-pre">{{ formatJson(ev.request_messages) }}</pre>
                    </el-tab-pane>
                    <el-tab-pane label="响应原文" name="raw">
                      <pre class="json-pre">{{ ev.response_raw || "(空)" }}</pre>
                    </el-tab-pane>
                    <el-tab-pane label="响应 JSON" name="json">
                      <pre class="json-pre">{{ formatJson(ev.response_json) }}</pre>
                    </el-tab-pane>
                  </el-tabs>
                </div>
              </el-collapse-transition>

              <el-button
                text
                type="primary"
                size="small"
                class="mt-1"
                @click="toggleDetail(ev)"
              >
                {{ expandedId === ev.id ? "收起" : "查看详情" }}
              </el-button>
            </div>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { ElMessage } from "element-plus"
import { LlmLogAPI, type AiRunEvent, type LlmLogSession, type MessageUsage } from "@/api/chat/llm-log"

// ── 会话 ──
const sessions = ref<LlmLogSession[]>([])
const activeSessionId = ref<number | null>(null)

async function loadSessions() {
  try {
    sessions.value = (await LlmLogAPI.getSessions()) || []
  } catch {
    sessions.value = []
  }
}

// ── 轮次列表（按 message_id 分组）──
interface RoundItem {
  message_id: number
  count: number
  time: string
  actions: string
}

const rounds = ref<RoundItem[]>([])
const roundsLoading = ref(false)

async function handleSessionChange() {
  rounds.value = []
  activeMessageId.value = null
  trace.value = []
  usage.value = null
  if (activeSessionId.value == null) return

  roundsLoading.value = true
  try {
    // 分页拉取该会话全部事件，前端按 message_id 分组
    const all: AiRunEvent[] = []
    let page = 1
    const pageSize = 100
    let total = 0
    do {
      const res = await LlmLogAPI.getPage({
        pageNum: page,
        pageSize,
        session_id: activeSessionId.value,
      })
      const list = res?.list || []
      all.push(...list)
      total = res?.total || 0
      page++
    } while (all.length < total)

    rounds.value = groupByMessage(all)
    if (rounds.value.length > 0) {
      selectRound(rounds.value[0].message_id)
    }
  } finally {
    roundsLoading.value = false
  }
}

function groupByMessage(events: AiRunEvent[]): RoundItem[] {
  const map = new Map<number, AiRunEvent[]>()
  for (const ev of events) {
    if (ev.message_id == null) continue
    if (!map.has(ev.message_id)) map.set(ev.message_id, [])
    map.get(ev.message_id)!.push(ev)
  }
  const result: RoundItem[] = []
  for (const [messageId, list] of map) {
    list.sort((a, b) => a.seq - b.seq)
    const actions = Array.from(new Set(list.map((e) => e.action))).join(" / ")
    result.push({
      message_id: messageId,
      count: list.length,
      time: list[0]?.create_time || "",
      actions,
    })
  }
  // 按 message_id 倒序（最新轮在前）
  result.sort((a, b) => b.message_id - a.message_id)
  return result
}

// ── 轨迹详情 ──
const trace = ref<AiRunEvent[]>([])
const traceLoading = ref(false)
const usage = ref<MessageUsage | null>(null)
const activeMessageId = ref<number | null>(null)
const expandedId = ref<number | null>(null)
const detailTab = ref("req")

async function selectRound(messageId: number) {
  activeMessageId.value = messageId
  traceLoading.value = true
  expandedId.value = null
  try {
    const [t, u] = await Promise.all([
      LlmLogAPI.getTrace(messageId),
      LlmLogAPI.getMessageUsage(messageId).catch(() => null),
    ])
    trace.value = t || []
    usage.value = u
  } finally {
    traceLoading.value = false
  }
}

function toggleDetail(ev: AiRunEvent) {
  if (expandedId.value === ev.id) {
    expandedId.value = null
  } else {
    expandedId.value = ev.id
    detailTab.value = "req"
  }
}

// ── 工具 ──
function eventTypeTag(t: string) {
  const map: Record<string, string> = {
    turn_start: "info",
    user_message: "",
    llm_call: "primary",
    tool_call: "warning",
    tool_result: "success",
    assistant_message: "success",
    turn_end: "info",
  }
  return (map[t] || "info") as any
}

function statusTag(s: string) {
  if (s === "success") return "success"
  if (s === "timeout") return "warning"
  return "danger"
}

function fmtNum(n: number) {
  return n?.toLocaleString() ?? "0"
}

function formatJson(obj: any) {
  if (obj == null) return "(空)"
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

async function copyTrace() {
  try {
    await navigator.clipboard.writeText(JSON.stringify(trace.value, null, 2))
    ElMessage.success("已复制")
  } catch {
    ElMessage.error("复制失败")
  }
}

onMounted(loadSessions)
</script>

<style scoped>
.ai-trace-page {
  display: flex;
  gap: 10px;
  height: calc(100vh - 108px);
  padding: 0;
}

.left-panel {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.left-panel :deep(.el-card__header) {
  padding: 8px 12px;
}

.left-panel :deep(.el-card__body) {
  padding: 10px 12px;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.round-list {
  flex: 1;
  overflow-y: auto;
}

.round-item {
  padding: 6px 10px;
  border-radius: 4px;
  cursor: pointer;
  margin-bottom: 5px;
  border: 1px solid transparent;
  transition: all 0.2s;
  background: #f7f8fa;
}

.round-item:hover {
  background: #eef1f6;
}

.round-item.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.round-id {
  font-weight: 600;
  font-size: 13px;
}

.round-count {
  font-size: 12px;
  color: var(--el-color-primary);
}

.round-time {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.round-actions {
  font-size: 12px;
  color: #606266;
  margin-top: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
  min-width: 0;
}

/* ── 紧凑单行用量栏 ── */
.usage-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid var(--el-border-color-lighter);
  font-size: 13px;
  flex-wrap: wrap;
}

.usage-title {
  font-weight: 600;
  color: #303133;
}

.usage-cell {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  white-space: nowrap;
}

.usage-cell em {
  font-style: normal;
  font-size: 12px;
  color: #909399;
}

.usage-cell {
  font-weight: 600;
  color: #303133;
}

.usage-cell i {
  font-style: normal;
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}

/* ── 调用链卡片占满剩余高度 ── */
.trace-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.trace-card :deep(.el-card__header) {
  padding: 8px 12px;
}

.trace-card :deep(.el-card__body) {
  padding: 8px 12px;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.trace-card :deep(.el-card__body) > div {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.trace-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.trace-node {
  padding: 6px 10px;
  border-radius: 4px;
  margin-bottom: 6px;
  background: #fafafa;
  border-left: 3px solid #dcdfe6;
}

.trace-node.status-error {
  border-left-color: var(--el-color-danger);
}

.trace-node.status-timeout {
  border-left-color: var(--el-color-warning);
}

.node-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
}

.node-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: 4px;
  font-size: 12px;
  color: #606266;
}

.meta-item {
  white-space: nowrap;
}

.node-error {
  margin-top: 4px;
  padding: 4px 8px;
  background: #fef0f0;
  color: var(--el-color-danger);
  border-radius: 4px;
  font-size: 12px;
}

.node-detail {
  margin-top: 6px;
}

.json-pre {
  background: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
  max-height: 50vh;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
