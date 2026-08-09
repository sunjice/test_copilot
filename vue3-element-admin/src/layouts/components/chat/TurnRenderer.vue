<template>
  <div class="turn-renderer" :class="{ 'is-streaming': isStreaming }">
    <template v-for="(seg, idx) in segments" :key="idx">
      <!-- 思考区块（可折叠） -->
      <div v-if="seg.type === 'thinking'" class="turn-thinking">
        <details class="thinking-details" :open="isStreaming && idx === segments.length - 1">
          <summary class="thinking-summary">
            <el-icon class="thinking-icon"><Loading v-if="isStreaming && idx === segments.length - 1 && !seg.content" class="is-loading" /><Tools v-else /></el-icon>
            <span class="thinking-label">{{ thinkingLabel(seg, idx) }}</span>
            <span v-if="segTitleDuration(seg) != null" class="thinking-elapsed">{{ segTitleDuration(seg) }}</span>
          </summary>
          <div v-if="seg.content" class="thinking-content" v-html="renderMarkdown(seg.content)" />
          <div v-else-if="isStreaming && idx === segments.length - 1" class="thinking-content thinking-empty">
            等待思考内容...
          </div>
        </details>
      </div>

      <!-- 工具区块（可展开查看详情） -->
      <details v-else-if="seg.type === 'tool'" class="turn-tool-details" :class="'tool--' + seg.status">
        <summary class="tool-summary">
          <span class="tool-icon">
            <el-icon v-if="seg.status === 'running'" class="is-loading tool-loading"><Loading /></el-icon>
            <el-icon v-else-if="seg.status === 'done'" class="tool-done"><CircleCheckFilled /></el-icon>
            <el-icon v-else class="tool-failed"><CircleCloseFilled /></el-icon>
          </span>
          <span class="tool-name">{{ toolDisplayName(seg.name) }}</span>
          <span v-if="seg.status === 'running'" class="tool-elapsed">
            {{ elapsedStr(seg.startedAt) }}
          </span>
          <span v-else-if="seg.durationMs != null" class="tool-duration">
            {{ formatDuration(seg.durationMs) }}
          </span>
          <span v-if="seg.status === 'failed' && seg.error" class="tool-error-summary">{{ seg.error }}</span>
        </summary>
        <div class="tool-detail-body">
          <div v-if="seg.argsSummary" class="tool-detail-row">
            <span class="tool-detail-label">参数</span>
            <span class="tool-detail-value">{{ seg.argsSummary }}</span>
          </div>
          <div class="tool-detail-row">
            <span class="tool-detail-label">耗时</span>
            <span class="tool-detail-value">
              {{ seg.status === 'running' ? elapsedStr(seg.startedAt) + '（执行中）' : seg.durationMs != null ? formatDuration(seg.durationMs) : '-' }}
            </span>
          </div>
          <div v-if="seg.status === 'failed' && seg.error" class="tool-detail-row">
            <span class="tool-detail-label">错误</span>
            <span class="tool-detail-value tool-detail-error">{{ seg.error }}</span>
          </div>
        </div>
      </details>

      <!-- 文本区块 -->
      <div v-else-if="seg.type === 'text'" class="turn-text" v-html="renderStreamText(seg.content, idx)" />
    </template>

    <!-- 流式光标 -->
    <span v-if="isStreaming && segments.length" class="turn-cursor">|</span>
  </div>
</template>

<script setup lang="ts">
import { Loading, CircleCheckFilled, CircleCloseFilled, Tools } from "@element-plus/icons-vue"
import { renderMarkdown, renderStreamingMarkdown } from "./utils"
import type { Segment } from "@/api/chat/types"

const props = withDefaults(defineProps<{
  segments: Segment[]
  isStreaming?: boolean
}>(), {
  isStreaming: false,
})

/** 工具名 → 中文显示名 */
const TOOL_NAMES: Record<string, string> = {
  list_projects: "列出项目",
  get_suite_tree: "查看模块树",
  search_cases: "搜索用例",
  get_case_detail: "查看用例详情",
  get_suite_samples: "查看样本用例",
  ask_question: "询问用户",
  create_core_select_task: "创建核心挑选任务",
  create_case_review_task: "创建审核任务",
  create_script_gen_task: "创建脚本生成任务",
  complete_case_steps: "补写测试步骤",
  create_case_complete_task: "完善用例",
  design_test_case: "设计测试用例",
}

function toolDisplayName(name: string): string {
  return TOOL_NAMES[name] || name
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

/** 当前已流逝时间（用于 running 态实时更新） */
function elapsedStr(startedAt: number): string {
  const elapsed = Math.round(performance.now() - startedAt)
  return formatDuration(elapsed)
}

/** 思考区块标题 */
function thinkingLabel(seg: Segment & { type: "thinking" }, _idx: number): string {
  if (seg.content) return "思考过程"
  // 流式中无内容显示"模型正在思考"，已结束时显示"思考完成"
  return props.isStreaming ? "模型正在思考" : "思考完成"
}

/** 思考区块耗时文本（流式时实时计算，历史时使用 durationMs） */
function segTitleDuration(seg: Segment & { type: "thinking" }): string | null {
  if (!seg.startedAt) return null
  const dur = seg.durationMs != null
    ? seg.durationMs
    : props.isStreaming ? Math.round(performance.now() - seg.startedAt) : null
  if (dur == null) return null
  return `（${formatDuration(dur)}）`
}

/** 流式模式下渲染文本：最后一个 text 区块用流式 Markdown，其余用完整 Markdown */
function renderStreamText(content: string, idx: number): string {
  const isLastText = idx === props.segments.length - 1 || props.segments[idx + 1]?.type !== "text"
  if (props.isStreaming && isLastText) {
    return renderStreamingMarkdown(content)
  }
  return renderMarkdown(content)
}
</script>

<style scoped>
.turn-renderer {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ── 思考区块 ── */
.thinking-details {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow: hidden;
}

.thinking-summary {
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

.thinking-summary:hover {
  background: var(--el-fill-color-light);
}

.thinking-icon {
  font-size: 12px;
  color: var(--el-color-primary);
}

.thinking-label {
  flex: 1;
}

.thinking-content {
  padding: 4px 8px 4px 20px;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--el-text-color-regular);
}

.thinking-empty {
  color: var(--el-text-color-placeholder);
  font-style: italic;
}

/* ── 工具区块（可展开 details） ── */
.turn-tool-details {
  border-radius: 6px;
  overflow: hidden;
  width: fit-content;
  min-width: 180px;
}

.turn-tool-details.tool--running {
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-5);
  color: var(--el-color-primary);
}

.turn-tool-details.tool--done {
  background: var(--el-color-success-light-9);
  border: 1px solid var(--el-color-success-light-5);
  color: var(--el-color-success);
}

.turn-tool-details.tool--failed {
  background: var(--el-color-danger-light-9);
  border: 1px solid var(--el-color-danger-light-5);
  color: var(--el-color-danger);
}

.tool-summary {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  font-size: 11px;
  line-height: 1.35;
  cursor: pointer;
  user-select: none;
  list-style: none;
  width: 100%;
  box-sizing: border-box;
}

.tool-summary::-webkit-details-marker {
  display: none;
}

.tool-summary::before {
  content: "▸";
  display: inline-block;
  font-size: 8px;
  margin-right: -1px;
  opacity: 0.5;
  transition: transform 0.15s;
  flex-shrink: 0;
}

.turn-tool-details[open] .tool-summary::before {
  transform: rotate(90deg);
}

.tool-icon {
  display: flex;
  align-items: center;
  font-size: 12px;
}

.tool-loading {
  animation: spin 1s linear infinite;
}

.tool-name {
  font-weight: 500;
}

.tool-elapsed {
  font-size: 10px;
  opacity: 0.7;
}

.tool-duration {
  font-size: 10px;
  opacity: 0.65;
}

.tool-error-summary {
  font-size: 10px;
  opacity: 0.85;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 展开的详情面板 */
.tool-detail-body {
  padding: 4px 8px 6px 22px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.tool-detail-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 11px;
  line-height: 1.45;
}

.tool-detail-label {
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
  min-width: 28px;
  font-weight: 500;
}

.tool-detail-value {
  color: var(--el-text-color-primary);
  word-break: break-word;
}

.tool-detail-error {
  color: var(--el-color-danger);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ── 文本区块 ── */
.turn-text {
  line-height: 1.55;
  font-size: 12.5px;
  color: var(--el-text-color-primary);
  word-break: break-word;
}

/* Markdown 渲染元素样式（与 ChatMessage .msg-text 保持一致） */
.turn-text :deep(p) {
  margin: 0 0 4px;
}
.turn-text :deep(p:last-child) {
  margin-bottom: 0;
}
.turn-text :deep(ul),
.turn-text :deep(ol) {
  padding-left: 16px;
  margin: 2px 0 4px;
}
.turn-text :deep(li) {
  margin-bottom: 1px;
}
.turn-text :deep(h1),
.turn-text :deep(h2),
.turn-text :deep(h3),
.turn-text :deep(h4) {
  margin: 6px 0 3px;
  font-weight: 600;
  line-height: 1.3;
}
.turn-text :deep(h1) { font-size: 15px; }
.turn-text :deep(h2) { font-size: 14px; }
.turn-text :deep(h3) { font-size: 13px; }
.turn-text :deep(h4) { font-size: 12.5px; }
.turn-text :deep(blockquote) {
  margin: 3px 0;
  padding: 2px 10px;
  border-left: 3px solid var(--el-color-primary-light-5);
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  border-radius: 0 6px 6px 0;
}
.turn-text :deep(table) {
  border-collapse: collapse;
  margin: 0;
  width: 100%;
  font-size: 11.5px;
}
.turn-text :deep(th),
.turn-text :deep(td) {
  border: 1px solid var(--el-border-color-lighter);
  padding: 2px 7px;
  text-align: left;
}
.turn-text :deep(th) {
  background: var(--el-fill-color-light);
  font-weight: 600;
}
.turn-text :deep(.md-table-wrapper) {
  margin: 6px 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow: hidden;
}
.turn-text :deep(.md-table-toolbar) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 8px;
  background: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.turn-text :deep(.md-table-label) {
  font-size: 10px;
  color: var(--el-text-color-secondary);
}
.turn-text :deep(.md-table-download) {
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
.turn-text :deep(.md-table-download:hover) {
  background: var(--el-color-primary-light-7);
  border-color: var(--el-color-primary);
}
.turn-text :deep(a) {
  color: var(--el-color-primary);
  text-decoration: underline;
}
.turn-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--el-border-color-lighter);
  margin: 5px 0;
}
.turn-text :deep(strong) {
  font-weight: 500;
  color: var(--el-text-color-primary);
}
.turn-text :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 0 3px;
  border-radius: 3px;
  font-size: 11px;
  font-family: "SF Mono", "Fira Code", Consolas, monospace;
}

/* 代码块 */
.turn-text :deep(.md-code-block) {
  background: #1e1e2e;
  border-radius: 6px;
  margin: 3px 0;
  overflow: hidden;
}
.turn-text :deep(.md-code-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 10px;
  background: rgba(255, 255, 255, 0.06);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.turn-text :deep(.md-code-lang) {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.55);
  text-transform: uppercase;
}
.turn-text :deep(.md-code-copy) {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.65);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  cursor: pointer;
  transition: all 0.15s;
}
.turn-text :deep(.md-code-copy:hover) {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}
.turn-text :deep(.hljs) {
  display: block;
  padding: 7px 10px;
  overflow-x: auto;
  font-size: 11px;
  line-height: 1.45;
  font-family: "SF Mono", "Fira Code", Consolas, monospace;
  color: #cdd6f4;
}
.turn-text :deep(.hljs-keyword) { color: #cba6f7; }
.turn-text :deep(.hljs-string) { color: #a6e3a1; }
.turn-text :deep(.hljs-number) { color: #fab387; }
.turn-text :deep(.hljs-comment) { color: #6c7086; font-style: italic; }
.turn-text :deep(.hljs-function) { color: #89b4fa; }
.turn-text :deep(.hljs-title) { color: #89b4fa; }
.turn-text :deep(.hljs-type) { color: #f9e2af; }
.turn-text :deep(.hljs-literal) { color: #fab387; }
.turn-text :deep(.hljs-built_in) { color: #f38ba8; }
.turn-text :deep(.hljs-attr) { color: #89b4fa; }
.turn-text :deep(.hljs-params) { color: #f2cdcd; }
.turn-text :deep(.hljs-meta) { color: #f5c2e7; }
.turn-text :deep(.hljs-property) { color: #89b4fa; }
.turn-text :deep(.hljs-variable) { color: #f38ba8; }
.turn-text :deep(.hljs-selector-class) { color: #a6e3a1; }
.turn-text :deep(.hljs-punctuation) { color: #bac2de; }
.turn-text :deep(.hljs-operator) { color: #89dceb; }
.turn-text :deep(.hljs-regexp) { color: #f38ba8; }

/* ── 流式光标 ── */
.turn-cursor {
  animation: blink 1s infinite;
  color: var(--el-color-primary);
  font-weight: bold;
  font-size: 12.5px;
  line-height: 1.55;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
</style>
