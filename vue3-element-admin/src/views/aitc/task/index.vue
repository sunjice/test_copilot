<template>
  <div class="aitc-task-page">
    <el-card>
      <div class="flex gap-2 items-center flex-wrap mb-4">
        <el-select v-model="queryParams.projectId" placeholder="项目" clearable style="width: 160px" @change="loadTasks">
          <el-option v-for="p in projectOptions" :key="p.value" :label="p.label" :value="String(p.value)" />
        </el-select>
        <el-select v-model="queryParams.taskType" placeholder="任务类型" clearable style="width: 140px" @change="loadTasks">
          <el-option v-for="(item, key) in TASK_TYPE_MAP" :key="key" :label="item.label" :value="key" />
        </el-select>
        <el-select v-model="queryParams.status" placeholder="状态" clearable style="width: 120px" @change="loadTasks">
          <el-option v-for="(item, key) in TASK_STATUS_MAP" :key="key" :label="item.label" :value="Number(key)" />
        </el-select>
        <el-button type="primary" @click="loadTasks">查询</el-button>
        <!-- <el-switch v-model="autoRefresh" active-text="自动刷新" size="small" style="margin-left: 8px" /> -->
      </div>

      <el-table :data="tableData" v-loading="loading" border stripe size="small">
        <el-table-column prop="id" label="任务ID" width="70" />
        <el-table-column prop="task_type" label="任务类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="taskTypeTag(row.task_type)" size="small">
              {{ taskTypeLabel(row.task_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="项目" width="140" show-overflow-tooltip />
        <el-table-column prop="suite_name" label="模块" min-width="180" show-overflow-tooltip />
        <el-table-column label="状态" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="150" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="row.total_count ? Math.round(row.done_count / row.total_count * 100) : 0"
              :status="row.status === TaskStatusEnum.FAILED ? 'exception' : row.status === TaskStatusEnum.COMPLETED ? 'success' : undefined"
              :stroke-width="16"
            />
            <span class="text-xs text-gray-500">{{ row.done_count }} / {{ row.total_count }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="create_by" label="创建人" width="90" />
        <el-table-column prop="create_time" label="创建时间" width="140" />
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <div class="ops-btns">
              <el-button text type="primary" size="small" @click="goDetail(row)">详情</el-button>
              <el-button
                v-if="row.status === TaskStatusEnum.QUEUED || row.status === TaskStatusEnum.RUNNING"
                text type="danger" size="small"
                v-hasPerm="'aitc:task:stop'" @click="stopTask(row)"
              >
                停止
              </el-button>
              <el-button
                v-if="row.status === TaskStatusEnum.COMPLETED || row.status === TaskStatusEnum.FAILED || row.status === TaskStatusEnum.CONFIRMED || row.status === TaskStatusEnum.STOPPED"
                text type="danger" size="small"
                v-hasPerm="'aitc:task:create'" @click="rerunTask(row)"
              >
                重跑
              </el-button>
              <el-button
                v-if="row.status === TaskStatusEnum.COMPLETED" text type="warning" size="small"
                v-hasPerm="'aitc:task:confirm'" @click="goReview(row)"
              >
                审核
              </el-button>
              <el-button text type="primary" size="small" @click="refreshProgress(row)">
                刷新
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && tableData.length === 0" description="暂无AI任务记录" />
      <div class="flex justify-end mt-4">
        <el-pagination
          v-model:current-page="queryParams.pageNum"
          v-model:page-size="queryParams.pageSize"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          :total="total"
          @size-change="loadTasks"
          @current-change="loadTasks"
        />
      </div>
    </el-card>


  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import ProjectAPI from "@/api/aitc/project";
import TaskAPI from "@/api/aitc/task";
import type { OptionItem, PageResult } from "@/api/common";
import type { TaskVO, TaskQueryParams, TaskItemVO } from "@/api/aitc/task";
import { TaskStatusEnum, ItemStatusEnum } from "@/enums/aitc";
import { TASK_TYPE_MAP, TASK_STATUS_MAP, taskTypeLabel, taskTypeTag, statusLabel, statusTag } from "../constants";
import { useTaskPolling } from "./shared/composables/useTaskPolling";
import { resolveReviewPath } from "./shared/utils/taskRouter";

const router = useRouter();

// ── 项目选项 ──
const projectOptions = ref<OptionItem[]>([]);

async function loadProjectOptions() {
  const res = await ProjectAPI.getOptions();
  projectOptions.value = res || [];
}

// ── 自动刷新 ──
const { autoRefresh } = useTaskPolling(loadTasks);

// ── 任务列表 ──
const tableData = ref<TaskVO[]>([]);
const loading = ref(false);
const total = ref(0);
const queryParams = reactive<TaskQueryParams>({
  pageNum: 1, pageSize: 20,
  projectId: undefined, taskType: undefined, status: undefined,
});

async function loadTasks(silent = false) {
  if (!silent) loading.value = true;
  try {
    const res = await TaskAPI.getPage(queryParams);
    const page = res as PageResult<TaskVO>;
    tableData.value = page?.list || (res as any)?.records || [];
    total.value = page?.total || (res as any)?.total || 0;
  } finally {
    loading.value = false;
  }
}

async function refreshProgress(row: TaskVO) {
  const res = await TaskAPI.getItems(String(row.id));
  const items = res as TaskItemVO[];
  const done = items?.filter(i => i.item_status !== ItemStatusEnum.PENDING).length || 0;
  row.done_count = done;
  const allDone = items?.every(i => i.item_status !== ItemStatusEnum.PENDING);
  if (allDone) {
    row.status = items?.every(i => i.item_status === ItemStatusEnum.SUCCESS) ? TaskStatusEnum.COMPLETED : TaskStatusEnum.FAILED;
  } else {
    row.status = TaskStatusEnum.RUNNING;
  }
}

async function rerunTask(row: TaskVO) {
  try {
    await ElMessageBox.confirm(
      `确认重新执行任务 #${row.id}？所有已有结果将被清空。`,
      "重跑确认",
      { type: "warning" }
    );
  } catch {
    return;
  }
  try {
    await TaskAPI.rerun(String(row.id));
    ElMessage.success("任务已重新启动");
    row.status = TaskStatusEnum.QUEUED;
    row.done_count = 0;
    loadTasks();
  } catch (e: any) {
    ElMessage.error(e?.message || "重跑失败");
  }
}

async function stopTask(row: TaskVO) {
  try {
    await ElMessageBox.confirm(
      `确认停止任务 #${row.id}？${row.status === TaskStatusEnum.RUNNING ? '正在执行的用例将中断。' : ''}`,
      "停止确认",
      { type: "warning", confirmButtonText: "确认停止" }
    );
  } catch {
    return;
  }
  try {
    await TaskAPI.stop(String(row.id));
    ElMessage.success("任务已停止");
    row.status = TaskStatusEnum.STOPPED;
    loadTasks();
  } catch (e: any) {
    ElMessage.error(e?.message || "停止失败");
  }
}

// ── 路由跳转
function goDetail(row: TaskVO) {
  router.push(`/aitc/tasks/${row.id}`);
}

function goReview(row: TaskVO) {
  // 异步加载子项，定位第一个可审核项后再跳转
  (async () => {
    try {
      const items = await TaskAPI.getItems(String(row.id)) as TaskItemVO[];
      const successItems = items?.filter(i => i.item_status === ItemStatusEnum.SUCCESS) || [];
      if (successItems.length > 0) {
        router.push(resolveReviewPath(row.task_type, String(row.id), String(successItems[0].id)));
      } else {
        router.push(`/aitc/tasks/${row.id}`);
      }
    } catch {
      router.push(`/aitc/tasks/${row.id}`);
    }
  })();
}

// ── 初始化 ──
onMounted(async () => {
  await loadProjectOptions();
  loadTasks();
});
</script>

<style scoped>
.aitc-task-page {
  padding: 4px;
}
.ops-btns {
  display: flex;
  align-items: center;
}
.ops-btns .el-button + .el-button {
  margin-left: 0;
}
</style>
