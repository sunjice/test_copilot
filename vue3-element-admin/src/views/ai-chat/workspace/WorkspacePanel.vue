<template>
  <div class="workspace-panel">
    <!-- 领域 Tab -->
    <div class="ws-tabs">
      <div
        v-for="domain in domainList"
        :key="domain.domain"
        class="ws-tab"
        :class="{ active: activeDomain === domain.domain, disabled: domain.disabled }"
        @click="switchDomain(domain)"
      >
        <span>{{ domain.label }}</span>
        <el-tag v-if="domain.disabled" size="small" type="info" effect="plain" class="ws-tag">
          建设中
        </el-tag>
      </div>
    </div>

    <!-- 领域主体 -->
    <div class="ws-body">
      <template v-if="!activeSchema || activeSchema.disabled">
        <el-empty description="该领域数据源建设中，敬请期待" :image-size="60" />
      </template>
      <template v-else>
        <!-- 项目下拉 -->
        <div class="ws-project">
          <el-select
            v-model="projectId"
            placeholder="选择项目"
            size="small"
            filterable
            clearable
            class="ws-project-select"
            @change="onProjectChange"
          >
            <el-option
              v-for="p in projectOptions"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
        </div>

        <!-- 模块/用例树 -->
        <div class="ws-tree-body">
          <el-tree
            v-if="projectId"
            ref="treeRef"
            :key="String(projectId)"
            :load="loadTreeNode"
            :props="treeProps"
            :filter-node-method="filterTree"
            lazy
            show-checkbox
            node-key="id"
            :expand-on-click-node="false"
            class="ws-tree"
            @check="onTreeCheck"
          >
            <template #default="{ data }">
              <template v-if="data.node_type === 'case'">
                <span class="ws-node ws-node-case" :title="data.name">
                  <el-icon class="ws-node-icon"><Document /></el-icon>
                  <span class="ws-node-label">{{ data.project_prefix }}{{ data.external_id }} {{ data.name }}</span>
                </span>
              </template>
              <template v-else>
                <span class="ws-node" :title="data.name">
                  <el-icon class="ws-node-icon"><FolderOpened /></el-icon>
                  <span class="ws-node-label">{{ data.name }}</span>
                  <span class="ws-node-count">({{ data.case_count }})</span>
                </span>
              </template>
            </template>
          </el-tree>
          <el-empty v-else description="请先选择项目" :image-size="50" />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue"
import { FolderOpened, Document } from "@element-plus/icons-vue"
import ProjectAPI from "@/api/aitc/project"
import SuiteAPI from "@/api/aitc/suite"
import type { SuiteNode } from "@/api/aitc/suite"
import type { OptionItem } from "@/api/common"
import { SCHEMAS, DOMAIN_ORDER, type DomainSchema } from "./schemas"

const emit = defineEmits<{
  (e: "context-change", ctx: Record<string, any>): void
}>()

// ── 领域 Tab ──
const domainList = computed(() => DOMAIN_ORDER.map((d) => SCHEMAS[d]).filter(Boolean))
const activeDomain = ref("case")
const activeSchema = computed<DomainSchema | null>(() => SCHEMAS[activeDomain.value] || null)

function switchDomain(d: DomainSchema) {
  if (d.disabled) return
  activeDomain.value = d.domain
  resetSelection()
}

// ── 项目 ──
const projectOptions = ref<OptionItem[]>([])
const projectId = ref<string | number | undefined>(undefined)

async function loadProjects() {
  try {
    projectOptions.value = await ProjectAPI.getOptions()
  } catch {
    projectOptions.value = []
  }
}

function onProjectChange(val: string | number | undefined) {
  // 项目变化：清空模块/用例选择
  selectedSuites.value = []
  selectedCases.value = []
  emitContext()
}

// ── 模块/用例树 ──
const treeRef = ref()
const treeProps = {
  children: "children",
  label: "label",
  isLeaf: (data: any) => data.node_type === "case",
}

function filterTree(value: string, data: any) {
  if (!value) return true
  const v = value.toLowerCase()
  return (data.name || "").toLowerCase().includes(v)
    || (data.label || "").toLowerCase().includes(v)
    || (data.external_id || "").toLowerCase().includes(v)
}

function loadTreeNode(node: any, resolve: (data: SuiteNode[]) => void) {
  if (node.level === 0) {
    // 根层：加载项目下的根级套件
    if (!projectId.value) {
      resolve([])
      return
    }
    SuiteAPI.getChildren(0, String(projectId.value)).then((res) => resolve(res || []))
  } else if (node.data.node_type === "case") {
    resolve([])
  } else {
    SuiteAPI.getChildren(node.data.id).then((res) => resolve(res || []))
  }
}

// ── 选择状态 ──
const selectedSuites = ref<{ id: string | number; label: string }[]>([])
const selectedCases = ref<{ id: string | number; label: string }[]>([])

function onTreeCheck(_data: any, _info: any) {
  // 提取所有勾选的叶子（用例）和套件节点
  const checkedLeaves = (treeRef.value?.getCheckedNodes(true) || []).filter(
    (n: any) => n.node_type === "case"
  )

  // 用例（叶子）
  selectedCases.value = checkedLeaves.map((n: any) => ({
    id: n.id,
    label: `${n.project_prefix || ""}${n.external_id || ""} ${n.name}`.trim(),
  }))

  // 套件（整层选中：勾选的 suite 节点）
  const checkedSuites = (treeRef.value?.getCheckedNodes() || []).filter(
    (n: any) => n.node_type === "suite"
  )
  selectedSuites.value = checkedSuites.map((n: any) => ({ id: n.id, label: n.name }))

  emitContext()
}

/** 清空选择 */
function resetSelection() {
  projectId.value = undefined
  selectedSuites.value = []
  selectedCases.value = []
  emitContext()
}

// ── 输出上下文 ──
function emitContext() {
  const ctx: Record<string, any> = {}
  if (projectId.value != null) {
    ctx.projectId = projectId.value
    const proj = projectOptions.value.find((p) => p.value === projectId.value)
    ctx.projectName = proj?.label || ""
  }
  if (selectedSuites.value.length === 1) {
    ctx.suiteId = selectedSuites.value[0].id
    ctx.suiteName = selectedSuites.value[0].label
  } else if (selectedSuites.value.length > 1) {
    ctx.suiteIds = selectedSuites.value.map((s) => s.id)
  }
  if (selectedCases.value.length) {
    ctx.selectedCaseIds = selectedCases.value.map((c) => c.id)
  }
  emit("context-change", ctx)
}

loadProjects()
</script>

<style scoped>
.workspace-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  background: var(--el-bg-color);
  overflow: hidden;
}

/* 领域 Tab */
.ws-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 10px 4px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
  flex-wrap: wrap;
}

.ws-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  color: var(--el-text-color-secondary);
  transition: all 0.15s;
  user-select: none;
}

.ws-tab:hover {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
}

.ws-tab.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 600;
}

.ws-tab.disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.ws-tag {
  height: 16px;
  line-height: 14px;
  font-size: 10px;
  padding: 0 4px;
}

/* 主体 */
.ws-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* 项目下拉 */
.ws-project {
  padding: 8px 10px 4px;
  flex-shrink: 0;
}

.ws-project-select {
  width: 100%;
}

/* 树主体 */
.ws-tree-body {
  flex: 1;
  overflow-y: auto;
  padding: 4px 6px;
  min-height: 0;
}

.ws-tree {
  font-size: 12px;
  background: transparent;
}

.ws-node {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.ws-node-icon {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.ws-node-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.ws-node-case .ws-node-label {
  font-size: 11px;
  color: var(--el-text-color-regular);
}

.ws-node-count {
  font-size: 10px;
  color: var(--el-text-color-placeholder);
  flex-shrink: 0;
}
</style>
