<template>
  <div class="core-review-page">
    <!-- 顶部 -->
    <div class="page-header">
      <div class="flex items-center gap-3">
        <el-button @click="goBack" icon="ArrowLeft" size="small">返回</el-button>
        <span class="text-lg font-bold">核心挑选审核 — 任务 #{{ taskId }}</span>
        <el-tag v-if="taskData" :type="taskStatusTag(taskData.status)" size="small">
          {{ taskStatusLabel(taskData.status) }}
        </el-tag>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar" v-loading="loading">
      <div class="flex items-center gap-3">
        <span class="text-sm text-gray-600">筛选：</span>
        <el-radio-group v-model="filterMode" size="small">
          <el-radio-button value="all">全部（{{ allItems.length }}）</el-radio-button>
          <el-radio-button value="core">只看核心（{{ coreItems.length }}）</el-radio-button>
          <el-radio-button value="non-core">只看非核心（{{ nonCoreItems.length }}）</el-radio-button>
        </el-radio-group>
      </div>
      <div class="flex items-center gap-4">
        <span class="text-sm text-gray-500">
          {{ filteredItems.length }} 条
          <template v-if="changedCount > 0">
            ，已修改 <b class="text-orange-500">{{ changedCount }}</b> 条
          </template>
        </span>
        <el-button
          type="primary"
          size="default"
          :loading="submitting"
          :disabled="allItems.length === 0"
          @click="handleSubmit"
        >
          提交审核
        </el-button>
      </div>
    </div>

    <!-- 表格 -->
    <div class="table-wrap" v-loading="loading">
      <el-table :data="filteredItems" border stripe size="small" height="100%">
        <el-table-column type="index" label="序号" width="55" align="center" />

        <el-table-column label="用例编号" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatCaseNumber(row) }}
          </template>
        </el-table-column>

        <el-table-column label="测试目的" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.purpose || row.case_name || '—' }}
          </template>
        </el-table-column>

        <el-table-column label="用例级别" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="importanceType(row.importance ?? 2)" size="small">
              {{ importanceLabel(row.importance ?? 2) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="AI 判定" width="85" align="center">
          <template #default="{ row }">
            <span v-if="aiSelected(row)" class="ai-core-tag">★ 核心</span>
            <span v-else class="ai-non-core-tag">非核心</span>
          </template>
        </el-table-column>

        <el-table-column label="AI 推荐理由" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="text-sm text-gray-600">{{ aiReason(row) || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="140" align="center" fixed="right">
          <template #default="{ row }">
            <el-button-group size="small">
              <el-button
                :type="userDecision(row) ? 'primary' : 'default'"
                @click="markCore(row)"
              >
                核心
              </el-button>
              <el-button
                :type="!userDecision(row) ? 'warning' : 'default'"
                @click="markNonCore(row)"
              >
                非核心
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useTagsViewStore } from "@/stores/tags-view"
import { ElMessage, ElMessageBox } from "element-plus"
import TaskAPI from "@/api/aitc/task"
import type { TaskVO, TaskItemVO, TaskConfirmItem } from "@/api/aitc/task"
import { ConfirmStatusEnum } from "@/enums/aitc"
import { importanceLabel, importanceType, statusLabel as taskStatusLabel, statusTag as taskStatusTag } from "../../constants"

const route = useRoute()
const router = useRouter()
const tagsViewStore = useTagsViewStore()
const taskId = String(route.params.taskId || "")

const loading = ref(false)
const submitting = ref(false)
const taskData = ref<TaskVO | null>(null)
const allItems = ref<TaskItemVO[]>([])

// 过滤模式
const filterMode = ref<"all" | "core" | "non-core">("all")

// 用户决策：true = 核心, false = 非核心
// key = item.id, 初始值跟随 AI 判定
const decisions = reactive<Record<string, boolean>>({})

// ── AI 判定工具 ──

function aiSelected(item: TaskItemVO): boolean {
  return !!item.output?.selected
}

function aiReason(item: TaskItemVO): string {
  return (item.output?.reason as string) || ""
}

// ── 用户决策工具 ──

function userDecision(item: TaskItemVO): boolean {
  return decisions[String(item.id)] ?? aiSelected(item)
}

function markCore(item: TaskItemVO) {
  decisions[String(item.id)] = true
}

function markNonCore(item: TaskItemVO) {
  decisions[String(item.id)] = false
}

// ── 筛选 ──

const coreItems = computed(() =>
  allItems.value.filter(it => aiSelected(it))
)

const nonCoreItems = computed(() =>
  allItems.value.filter(it => !aiSelected(it))
)

const filteredItems = computed(() => {
  if (filterMode.value === "core") return coreItems.value
  if (filterMode.value === "non-core") return nonCoreItems.value
  return allItems.value
})

// ── 统计 ──

const changedCount = computed(() => {
  return allItems.value.filter(it => {
    const id = String(it.id)
    return decisions[id] !== undefined && decisions[id] !== aiSelected(it)
  }).length
})

// ── 用例编号 ──

function formatCaseNumber(row: TaskItemVO): string {
  const prefix = (row.project_prefix || "") + (row.external_id || "")
  const name = row.case_name || ""
  if (prefix && name) return prefix + "__" + name
  return name || prefix || "—"
}

// ── 加载数据 ──

async function loadData() {
  loading.value = true
  try {
    const res = await TaskAPI.getDetail(taskId)
    const detail = res as any
    taskData.value = detail?.task || null
    allItems.value = (detail?.items || []) as TaskItemVO[]

    // 初始化用户决策为 AI 判定
    for (const it of allItems.value) {
      const id = String(it.id)
      if (decisions[id] === undefined) {
        decisions[id] = aiSelected(it)
      }
    }
  } finally {
    loading.value = false
  }
}

// ── 提交 ──

async function handleSubmit() {
  if (allItems.value.length === 0) {
    ElMessage.warning("没有可审核的项")
    return
  }

  await ElMessageBox.confirm(
    `确认提交审核？共 ${allItems.value.length} 条，标记为核心 ${coreConfirmCount.value} 条，非核心 ${nonCoreConfirmCount.value} 条。`,
    "确认提交",
    { confirmButtonText: "确定", cancelButtonText: "取消", type: "warning" }
  )

  submitting.value = true
  try {
    const items: TaskConfirmItem[] = allItems.value.map(it => {
      const finalIsCore = userDecision(it)
      const aiSelectedCore = aiSelected(it)
      // 未改动 AI 建议 = 采纳；改动过 = 编辑采纳
      const confirm_status = finalIsCore === aiSelectedCore
        ? ConfirmStatusEnum.ACCEPTED
        : ConfirmStatusEnum.EDIT_ACCEPTED
      return {
        item_id: String(it.id),
        confirm_status,
        is_core: finalIsCore,
      }
    })

    await TaskAPI.confirm(taskId, { items })
    ElMessage.success("审核完成，结果已应用")
    goBack()
  } catch (e: any) {
    if (e !== "cancel") {
      ElMessage.error(e?.message || "提交失败")
    }
  } finally {
    submitting.value = false
  }
}

const coreConfirmCount = computed(() =>
  allItems.value.filter(it => userDecision(it)).length
)

const nonCoreConfirmCount = computed(() =>
  allItems.value.filter(it => !userDecision(it)).length
)

function goBack() {
  // 先 replace 回任务详情（不新增历史/标签），再删除当前审核页标签
  const currentTag = {
    name: route.name as string,
    title: route.meta.title as string,
    path: route.path,
    fullPath: route.fullPath,
    icon: route.meta?.icon as string | undefined,
    affix: route.meta?.affix,
    keepAlive: route.meta?.keepAlive,
    query: { ...route.query },
  }
  router.replace(`/aitc/tasks/${taskId}`).then(() => {
    tagsViewStore.delView(currentTag)
  })
}

onMounted(() => loadData())
</script>

<style scoped>
.core-review-page {
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
  padding: 4px;
}

.page-header {
  padding: 8px 4px;
  flex-shrink: 0;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.table-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.ai-core-tag {
  color: #67c23a;
  font-weight: 700;
  font-size: 13px;
}

.ai-non-core-tag {
  color: #c0c4cc;
  font-size: 13px;
}
</style>
