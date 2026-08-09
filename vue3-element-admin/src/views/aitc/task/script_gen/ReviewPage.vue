<template>
  <div class="script-review-page">
    <!-- 顶部导航 -->
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <el-button @click="goBack" icon="ArrowLeft" size="small">返回</el-button>
        <span class="text-lg font-bold">脚本审核 — 任务 #{{ taskId }}</span>
        <el-tag v-if="caseData" type="info" size="small">{{ caseData.name }}</el-tag>
      </div>
      <div class="flex gap-2">
        <el-button @click="prevItem" :disabled="!hasPrev" size="small">上一条</el-button>
        <span class="text-sm text-gray-500 py-1">{{ currentIndex + 1 }} / {{ allItems.length }}</span>
        <el-button @click="nextItem" :disabled="!hasNext" size="small">下一条</el-button>
      </div>
    </div>

    <!-- 左右分栏 -->
    <div class="review-split" v-loading="loading">
      <!-- 左侧：用例详情（只读） -->
      <div class="review-panel review-left">
        <div class="panel-header">
          <span class="panel-title">测试用例（参考）</span>
        </div>
        <div class="panel-body">
          <div class="field-block">
            <div class="field-label">用例名称</div>
            <div class="field-value">{{ caseData?.name || '—' }}</div>
          </div>
          <div class="field-block">
            <div class="field-label">测试思想</div>
            <div class="field-value pre-wrap">{{ caseData?.summary || '—' }}</div>
          </div>
          <div class="field-block">
            <div class="field-label">前置条件</div>
            <div class="field-value pre-wrap">{{ caseData?.preconditions || '—' }}</div>
          </div>
          <div class="field-block">
            <div class="field-label">测试数据</div>
            <div class="field-value pre-wrap">{{ caseData?.test_data || '—' }}</div>
          </div>
          <div class="field-block">
            <div class="field-label">测试步骤</div>
            <el-table v-if="caseData?.steps?.length" :data="caseData.steps" border size="small" class="step-table">
              <el-table-column prop="step_no" label="#" width="45" />
              <el-table-column prop="action" label="操作步骤" />
              <el-table-column prop="expected" label="预期结果" />
            </el-table>
            <div v-else class="text-gray-400 text-sm">—</div>
          </div>
          <div class="field-block">
            <div class="field-label">级别</div>
            <div class="field-value">{{ importanceLabel(caseData?.importance) }}</div>
          </div>
        </div>
      </div>

      <!-- 右侧：AI 生成脚本（可编辑） -->
      <div class="review-panel review-right">
        <div class="panel-header">
          <span class="panel-title">AI 生成脚本（可编辑）</span>
          <div class="flex gap-2 items-center">
            <el-tag size="small">{{ scriptLanguage }} / {{ scriptFramework }}</el-tag>
            <el-button size="small" type="primary" plain @click="formatScript">格式化</el-button>
          </div>
        </div>
        <div class="panel-body script-editor-body">
          <!-- 脚本元信息 -->
          <div class="flex gap-4 mb-3 flex-wrap">
            <el-form-item label="语言" label-width="50px" size="small">
              <el-input v-model="scriptLanguage" size="small" style="width: 100px" />
            </el-form-item>
            <el-form-item label="框架" label-width="50px" size="small">
              <el-input v-model="scriptFramework" size="small" style="width: 120px" />
            </el-form-item>
          </div>

          <!-- 脚本编辑区 -->
          <el-input
            v-model="scriptContent"
            type="textarea"
            :rows="20"
            placeholder="在此查看和编辑 AI 生成的脚本..."
            class="script-editor"
          />
        </div>
      </div>
    </div>

    <!-- 底部提交 -->
    <div class="review-footer mt-4 flex justify-center gap-3">
      <el-button size="large" @click="goBack">返回</el-button>
      <el-button size="large" type="warning" @click="submitIgnore" :loading="submitting">忽略</el-button>
      <el-button size="large" type="primary" @click="submitAccept" :loading="submitting">
        采纳并入库
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useTagsViewStore } from "@/stores/tags-view";
import { ElMessage } from "element-plus";
import TaskAPI from "@/api/aitc/task";
import type { CaseVO } from "@/api/aitc/case";
import type { TaskItemVO } from "@/api/aitc/task";
import { importanceLabel } from "../../constants";
import { ConfirmStatusEnum } from "@/enums/aitc";

const route = useRoute();
const router = useRouter();
const tagsViewStore = useTagsViewStore();
const taskId = String(route.params.taskId || "");
const itemId = String(route.params.itemId || "");

const loading = ref(false);
const submitting = ref(false);
const caseData = ref<CaseVO | null>(null);
const itemData = ref<TaskItemVO | null>(null);
const allItems = ref<TaskItemVO[]>([]);

// 脚本编辑
const scriptContent = ref("");
const scriptLanguage = ref("python");
const scriptFramework = ref("pytest");

const aiOutput = computed(() => itemData.value?.output as Record<string, any> | null);

const currentIndex = computed(() => allItems.value.findIndex(it => String(it.id) === itemId));
const hasPrev = computed(() => currentIndex.value > 0);
const hasNext = computed(() => currentIndex.value < allItems.value.length - 1);

function formatScript() {
  // 简单缩进美化
  try {
    const lines = scriptContent.value.split("\n");
    let indent = 0;
    const formatted = lines.map(line => {
      const trimmed = line.trim();
      if (!trimmed) return "";
      if (trimmed.startsWith("}") || trimmed.startsWith(")") || trimmed.startsWith("]") ||
          trimmed.startsWith("elif") || trimmed.startsWith("else") || trimmed.startsWith("except") ||
          trimmed.startsWith("finally")) {
        indent = Math.max(0, indent - 1);
      }
      const result = "    ".repeat(indent) + trimmed;
      if (trimmed.endsWith("{") || trimmed.endsWith("(") || trimmed.endsWith("[") ||
          trimmed.endsWith(":") && !trimmed.startsWith("http")) {
        indent += 1;
      }
      return result;
    });
    scriptContent.value = formatted.join("\n");
  } catch { /* ignore */ }
}

// 导航
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
  };
  router.replace(`/aitc/tasks/${taskId}`).then(() => {
    tagsViewStore.delView(currentTag);
  });
}

function prevItem() {
  if (!hasPrev.value) return;
  const prev = allItems.value[currentIndex.value - 1];
  router.replace(`/aitc/tasks/${taskId}/script-review/${prev.id}`);
  loadItem(String(prev.id));
}

function nextItem() {
  if (!hasNext.value) return;
  const next = allItems.value[currentIndex.value + 1];
  router.replace(`/aitc/tasks/${taskId}/script-review/${next.id}`);
  loadItem(String(next.id));
}

// 数据加载
async function loadItem(id?: string) {
  const targetId = id || itemId;
  loading.value = true;
  try {
    const itemsRes = await TaskAPI.getItems(taskId);
    allItems.value = (itemsRes as TaskItemVO[]) || [];

    const res = await TaskAPI.getItemWithCase(taskId, targetId);
    const data = res as any;
    itemData.value = data?.item || null;
    caseData.value = data?.case || null;

    // 初始化脚本内容
    const output = itemData.value?.output as any;
    scriptContent.value = output?.script || "";
    scriptLanguage.value = output?.language || "python";
    scriptFramework.value = output?.framework || "pytest";
  } finally {
    loading.value = false;
  }
}

// 提交
async function submitAccept() {
  if (!itemData.value) return;
  submitting.value = true;
  try {
    await TaskAPI.reviewItem(taskId, String(itemData.value.id), {
      task_id: taskId,
      item_id: String(itemData.value.id),
      confirm_status: ConfirmStatusEnum.EDIT_ACCEPTED, // 编辑采纳
      fields: [],
      final_content: scriptContent.value,
    });

    ElMessage.success("脚本已采纳并入库");
    if (hasNext.value) {
      nextItem();
    } else {
      goBack();
    }
  } catch (e: any) {
    ElMessage.error(e?.message || "提交失败");
  } finally {
    submitting.value = false;
  }
}

async function submitIgnore() {
  if (!itemData.value) return;
  submitting.value = true;
  try {
    await TaskAPI.reviewItem(taskId, String(itemData.value.id), {
      task_id: taskId,
      item_id: String(itemData.value.id),
      confirm_status: ConfirmStatusEnum.IGNORED,
      fields: [],
    });

    ElMessage.success("已忽略");
    if (hasNext.value) {
      nextItem();
    } else {
      goBack();
    }
  } catch (e: any) {
    ElMessage.error(e?.message || "提交失败");
  } finally {
    submitting.value = false;
  }
}

// 监听路由变化
import { watch } from "vue";
watch(() => route.params.itemId, (newId) => {
  if (newId) loadItem(String(newId));
});

onMounted(() => loadItem());
</script>

<style scoped>
.script-review-page {
  padding: 4px;
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
}

.review-split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.review-panel {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.review-left {
  background: #fafafa;
}

.review-right {
  background: #fafdf5;
}

.panel-header {
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-shrink: 0;
}

.panel-title {
  font-weight: 700;
  font-size: 14px;
}

.panel-body {
  padding: 12px 16px;
  overflow-y: auto;
  flex: 1;
}

.script-editor-body {
  padding: 12px 16px;
  overflow-y: auto;
  flex: 1;
}

.field-block {
  margin-bottom: 16px;
}

.field-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
  font-weight: 600;
}

.field-value {
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
}

.pre-wrap {
  white-space: pre-wrap;
  margin: 0;
  font-family: inherit;
  font-size: 13px;
}

.step-table {
  width: 100%;
}

.script-editor :deep(textarea) {
  font-family: "Consolas", "Monaco", "Courier New", monospace;
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  height: calc(100vh - 340px) !important;
}

.review-footer {
  flex-shrink: 0;
}
</style>
