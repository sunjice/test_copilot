<template>
  <div class="aitc-task-detail-page">
    <TaskProgress :task-id="taskId" :task="task" @go-review="goReview" @rerun="rerunTask" @stop="stopTask">
      <template #header-left>
        <el-button @click="goBack" icon="ArrowLeft" size="small">返回</el-button>
      </template>
      <template #header-right>
        <el-switch v-model="autoRefresh" active-text="自动刷新" size="small" style="margin-left: 12px" />
      </template>
    </TaskProgress>

    <ReviewRecordList v-if="task?.task_type === 'case_review'" :records="reviewRecords" />

    <!-- 明细列表 -->
    <el-card>
      <template #header>
        <div class="flex justify-between items-center">
          <span class="font-bold">任务明细（{{ items.length }} 条）</span>
          <div class="flex gap-2">
            <el-input v-model="itemKeyword" placeholder="搜索用例编号" clearable size="small" style="width: 200px" />
          </div>
        </div>
      </template>
      <el-table :data="filteredItems" v-loading="loading" border stripe size="small">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column label="用例编号" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatCaseNumber(row) }}
          </template>
        </el-table-column>
        <el-table-column label="明细状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="itemStatusTag(row.item_status)" size="small">
              {{ itemStatusLabel(row.item_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="确认状态" width="90" align="center">
          <template #default="{ row }">
            <template v-if="task?.task_type === 'core_select'">
              <el-tag
                v-if="row.confirm_status === ConfirmStatusEnum.PENDING"
                type="info"
                size="small"
              >
                待确认
              </el-tag>
              <el-tag
                v-else-if="row.confirm_status === ConfirmStatusEnum.IGNORED"
                size="small"
              >
                忽略
              </el-tag>
              <el-tag
                v-else
                :type="coreSelectAdopted(row) ? 'success' : 'warning'"
                size="small"
              >
                {{ coreSelectAdopted(row) ? '已采纳' : '未采纳' }}
              </el-tag>
            </template>
            <el-tag v-else :type="confirmTag(row.confirm_status)" size="small">
              {{ confirmLabel(row.confirm_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="AI输出" min-width="220">
          <template #default="{ row }">
            <template v-if="row.output">
              <OutputCoreSelect
                v-if="task?.task_type === 'core_select'"
                :output="row.output"
              />
              <OutputCaseReview
                v-else-if="task?.task_type === 'case_review'"
                :output="row.output"
              />
              <OutputScriptGen
                v-else-if="task?.task_type === 'script_gen'"
                :output="row.output"
              />
              <div v-else class="text-xs text-gray-400">{{ JSON.stringify(row.output).slice(0, 80) }}</div>
            </template>
            <span v-else class="text-gray-300">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.item_status === ItemStatusEnum.SUCCESS && row.confirm_status === ConfirmStatusEnum.PENDING && (row.output?.rewritten || row.output?.fields || row.output?.script)"
              text type="primary" size="small"
              @click="goReviewItem(row)"
            >
              审核
            </el-button>
            <el-button
              v-if="row.item_status === ItemStatusEnum.SUCCESS && row.output"
              text type="info" size="small"
              @click="showRawOutput(row)"
              class="ml-1"
            >
              原始
            </el-button>
            <span v-else-if="row.item_status === ItemStatusEnum.PENDING" class="text-xs text-gray-400">等待中</span>
            <span v-else-if="row.item_status === ItemStatusEnum.FAILED" class="text-xs text-red-400">失败</span>
            <span v-else-if="row.confirm_status > ConfirmStatusEnum.PENDING" class="text-xs text-gray-400">已确认</span>
            <span v-else class="text-xs text-gray-300">—</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && items.length === 0" description="暂无明细" />
    </el-card>

    <!-- 原始 AI 输出查看弹窗 -->
    <el-dialog v-model="rawOutputVisible" title="AI 原始输出" width="700px" destroy-on-close>
      <div class="raw-output-header">
        <span class="text-sm font-bold">{{ rawOutputCaseName }}</span>
        <el-tag :type="rawOutputItemStatus === ItemStatusEnum.SUCCESS ? 'success' : 'danger'" size="small" class="ml-2">
          {{ rawOutputItemStatus === ItemStatusEnum.SUCCESS ? '成功' : '失败' }}
        </el-tag>
        <el-button size="small" text @click="copyRawOutput" class="ml-2">复制</el-button>
      </div>
      <pre class="raw-output-json">{{ rawOutputFormatted }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import TaskAPI from "@/api/aitc/task";
import type { TaskVO, TaskItemVO, ReviewRecordVO } from "@/api/aitc/task";
import { ItemStatusEnum, ConfirmStatusEnum, TaskStatusEnum } from "@/enums/aitc";
import {
  confirmLabel, confirmTag,
  itemStatusLabel, itemStatusTag,
} from "../constants";
import TaskProgress from "./shared/components/TaskProgress.vue";
import ReviewRecordList from "./shared/components/ReviewRecordList.vue";
import { useTaskPolling } from "./shared/composables/useTaskPolling";
import { resolveReviewPath } from "./shared/utils/taskRouter";
import OutputCoreSelect from "./core_select/OutputColumn.vue";
import OutputCaseReview from "./case_review/OutputColumn.vue";
import OutputScriptGen from "./script_gen/OutputColumn.vue";

const route = useRoute();
const router = useRouter();
const taskId = String(route.params.taskId || "");

const task = ref<TaskVO | null>(null);
const items = ref<TaskItemVO[]>([]);
const reviewRecords = ref<ReviewRecordVO[]>([]);
const loading = ref(false);
const itemKeyword = ref("");
// 自动刷新
const { autoRefresh } = useTaskPolling(loadData, 1000);

// 格式化用例编号：project_prefix + external_id + __ + case_name
function formatCaseNumber(row: TaskItemVO): string {
  const prefix = (row.project_prefix || "") + (row.external_id || "");
  const name = row.case_name || "";
  if (prefix && name) return prefix + "__" + name;
  return name || prefix || "—";
}

// 核心挑选：AI建议与最终结果是否一致
function coreSelectAdopted(row: TaskItemVO): boolean {
  const aiSelected = row.output?.selected ?? false;
  const finalIsCore = row.is_core !== null && row.is_core !== undefined
    ? row.is_core
    : aiSelected;
  return aiSelected === finalIsCore;
}

// 原始输出弹窗
const rawOutputVisible = ref(false);
const rawOutputContent = ref<Record<string, any> | null>(null);
const rawOutputCaseName = ref("");
const rawOutputItemStatus = ref(0);

const rawOutputFormatted = computed(() => {
  if (!rawOutputContent.value) return "";
  try {
    return JSON.stringify(rawOutputContent.value, null, 2);
  } catch {
    return String(rawOutputContent.value);
  }
});

const filteredItems = computed(() => {
  if (!itemKeyword.value) return items.value;
  const kw = itemKeyword.value.toLowerCase();
  return items.value.filter(it => {
    const prefix = (it.project_prefix || "").toLowerCase();
    const extId = (it.external_id || "").toLowerCase();
    const name = (it.case_name || "").toLowerCase();
    return (prefix + extId + name).includes(kw);
  });
});

// 原材料输出弹窗
function showRawOutput(row: TaskItemVO) {
  rawOutputContent.value = row.output || null;
  rawOutputCaseName.value = formatCaseNumber(row);
  rawOutputItemStatus.value = row.item_status;
  rawOutputVisible.value = true;
}

async function copyRawOutput() {
  try {
    await navigator.clipboard.writeText(rawOutputFormatted.value);
    ElMessage.success("已复制到剪贴板");
  } catch {
    ElMessage.warning("复制失败，请手动复制");
  }
}

// 数据加载
async function loadData(silent = false) {
  if (!silent) loading.value = true;
  try {
    const res = await TaskAPI.getDetail(taskId);
    const detail = res as any;
    task.value = detail?.task || null;
    items.value = detail?.items || [];

    // 加载审核记录
    try {
      const records = await TaskAPI.getReviewRecords(taskId);
      reviewRecords.value = records || [];
    } catch { /* ignore */ }
  } finally {
    loading.value = false;
  }
}

// 路由跳转
function goBack() {
  router.push("/aitc/tasks");
}

function goReview() {
  // 根据任务类型跳转，默认从第一条开始审核
  const taskType = task.value?.task_type;
  if (items.value.length > 0 && taskType) {
    router.push(resolveReviewPath(taskType, taskId, String(items.value[0].id)));
  }
}

function goReviewItem(row: TaskItemVO) {
  const taskType = task.value?.task_type;
  if (!taskType) return;
  router.push(resolveReviewPath(taskType, taskId, String(row.id)));
}

async function rerunTask() {
  try {
    await ElMessageBox.confirm("确认重新执行？所有结果将被清空。", "重跑确认", { type: "warning" });
  } catch {
    return;
  }
  try {
    await TaskAPI.rerun(taskId);
    ElMessage.success("任务已重新启动");
    loadData();
  } catch (e: any) {
    ElMessage.error(e?.message || "重跑失败");
  }
}

async function stopTask() {
  try {
    await ElMessageBox.confirm(
      task.value?.status === TaskStatusEnum.RUNNING
        ? "确认停止任务？正在执行的用例将中断。"
        : "确认停止任务？",
      "停止确认",
      { type: "warning", confirmButtonText: "确认停止" }
    );
  } catch {
    return;
  }
  try {
    await TaskAPI.stop(taskId);
    ElMessage.success("任务已停止");
    loadData();
  } catch (e: any) {
    ElMessage.error(e?.message || "停止失败");
  }
}

onMounted(() => {
  loadData();
});

// 从审核页返回时静默刷新（keep-alive 的 key 复用不触发 onMounted）
watch(() => route.fullPath, () => {
  loadData(true);
});
</script>

<style scoped>
.aitc-task-detail-page {
  padding: 4px;
}

.raw-output-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.raw-output-json {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.7;
  max-height: 500px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
</style>
