<template>
  <div class="case-review-page">
    <!-- 顶部导航（紧凑单行） -->
    <div class="header-bar">
      <div class="header-left">
        <el-button @click="goBack" icon="ArrowLeft" size="small">返回</el-button>
        <span class="page-title">用例审核 — 任务 #{{ taskId }}</span>
        <span v-if="caseData" class="case-name">{{ caseNumber }}</span>
      </div>
      <div class="header-center" v-if="aiOutput">
        <span class="stat-pass">{{ passCount }} 合格</span>
        <span class="stat-divider">/</span>
        <span class="stat-fail">{{ failCount }} 不合格</span>
        <template v-if="failCount > 0">
          <span class="stat-processed">（已处理 {{ processedCount }}/{{ failCount }}）</span>
        </template>
      </div>
      <div class="header-right">
        <span class="count-text">{{ currentIndex + 1 }} / {{ allItems.length }}</span>
        <el-button @click="prevItem" :disabled="!hasPrev" size="small">上一条</el-button>
        <el-button @click="nextItem" :disabled="!hasNext" size="small">下一条</el-button>
        <el-button v-if="failCount > 0" size="small" type="success" plain @click="doAcceptAll">全部采纳</el-button>
        <el-button v-if="failCount > 0" size="small" type="warning" plain @click="doIgnoreAll">全部忽略</el-button>
        <el-button size="small" type="info" text @click="showRawDialog" v-if="rawOutput">原始输出</el-button>
      </div>
    </div>

    <!-- 主体：左右两个大框 -->
    <div class="main-body" v-loading="loading">
      <div v-if="!caseData" class="empty-wrapper">
        <el-empty description="未加载到用例数据" :image-size="80" />
      </div>

      <div v-else class="two-panel">
        <!-- 左侧：原始用例详情 -->
        <div class="panel panel-left">
          <div class="panel-header">
            <span class="panel-title">原始用例详情</span>
            <span class="panel-badge">只读</span>
          </div>
          <div class="panel-body">
            <table class="detail-table">
              <tbody>
                <tr v-for="f in caseFields" :key="f.key">
                  <td class="detail-label">{{ f.label }}</td>
                  <td class="detail-value">
                    <template v-if="f.key === 'steps'">
                      <el-table
                        v-if="(f.value || []).length"
                        :data="f.value"
                        border
                        size="small"
                        class="mini-step-table"
                      >
                        <el-table-column prop="step_no" label="#" width="40" />
                        <el-table-column prop="action" label="操作步骤" min-width="120" />
                        <el-table-column prop="expected" label="预期结果" min-width="120" />
                      </el-table>
                      <span v-else class="empty-text">（空）</span>
                    </template>
                    <span v-else-if="f.key === 'name'">{{ caseNumber }}</span>
                    <span v-else-if="f.key === 'importance'">{{ f.value != null ? importanceLabel(f.value) : '（空）' }}</span>
                    <span v-else>{{ displayVal(f.value) }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 右侧：AI 审核意见 -->
        <div class="panel panel-right">
          <div class="panel-header">
            <span class="panel-title">AI 审核意见</span>
            <span v-if="failCount > 0" class="panel-badge badge-fail-bg">待处理 {{ processedCount }}/{{ failCount }}</span>
            <span v-else class="panel-badge badge-pass-bg">全部通过</span>
          </div>
          <div class="panel-body">
            <!-- 评分卡片 -->
            <div v-if="aiOutput" class="score-card">
              <div class="score-ring">
                <span class="score-num">{{ aiOutput.score ?? '—' }}</span>
                <span class="score-unit">分</span>
              </div>
              <div class="score-info">
                <div class="score-label">AI 评分</div>
                <div v-if="aiOutput.overall_assessment" class="score-assessment">{{ aiOutput.overall_assessment }}</div>
                <div v-else class="score-assessment">暂无整体评估</div>
              </div>
            </div>

            <!-- 字段校验结果：仅不合格字段 -->
            <div class="suggestions-list">
              <div class="box-title">AI 字段建议</div>
              <div v-if="!failFields.length" class="all-pass-tip">
                <el-icon color="#67c23a" :size="18"><CircleCheck /></el-icon>
                <span>所有字段均合格，无需 AI 修正</span>
              </div>

              <div
                v-for="f in failFields"
                :key="f.field_name"
                class="suggestion-card"
                :class="{
                  'suggestion-accepted': fieldStates[f.field_name] === 'accept',
                  'suggestion-ignored': fieldStates[f.field_name] === 'ignore',
                  'suggestion-manual': fieldStates[f.field_name] === 'manual',
                }"
              >
                <div class="suggestion-header">
                  <span class="suggestion-field">{{ fieldLabelMap[f.field_name] || f.field_name }}</span>
                  <div class="suggestion-badges">
                    <span v-if="fieldStates[f.field_name] === 'accept'" class="badge badge-state-accept">已采纳</span>
                    <span v-else-if="fieldStates[f.field_name] === 'ignore'" class="badge badge-state-ignore">已忽略</span>
                    <span v-else-if="fieldStates[f.field_name] === 'manual'" class="badge badge-state-manual">已修改</span>
                    <span v-else class="badge badge-fail">待处理</span>
                  </div>
                </div>

                <div v-if="f.rule_violated" class="reason-row">
                  <span class="reason-label">理由：</span>
                  <span class="reason-text">{{ f.rule_violated }}</span>
                </div>

                <div class="suggestion-value">
                  <template v-if="fieldStates[f.field_name] === 'ignore'">
                    <span class="ignored-tip">已忽略 AI 建议，保持原值</span>
                  </template>

                  <template v-else-if="fieldStates[f.field_name] === 'accept'">
                    <template v-if="f.field_name === 'steps'">
                      <el-table
                        v-if="(f.suggested || []).length"
                        :data="f.suggested"
                        border
                        size="small"
                        class="mini-step-table"
                      >
                        <el-table-column prop="step_no" label="#" width="40" />
                        <el-table-column prop="action" label="操作步骤" min-width="120" />
                        <el-table-column prop="expected" label="预期结果" min-width="120" />
                      </el-table>
                      <span v-else class="empty-text">（空）</span>
                    </template>
                    <span v-else class="suggested-text">{{ displayVal(f.suggested) }}</span>
                  </template>

                  <template v-else-if="fieldStates[f.field_name] === 'manual'">
                    <template v-if="f.field_name === 'steps'">
                      <el-table
                        v-if="manualSteps.length"
                        :data="manualSteps"
                        border
                        size="small"
                        class="mini-step-table"
                      >
                        <el-table-column prop="step_no" label="#" width="40" />
                        <el-table-column prop="action" label="操作步骤" min-width="120" />
                        <el-table-column prop="expected" label="预期结果" min-width="120" />
                      </el-table>
                      <span v-else class="empty-text">（空）</span>
                    </template>
                    <span v-else class="suggested-text">{{ manualValues[f.field_name] }}</span>
                  </template>

                  <template v-else>
                    <!-- 步骤字段：编辑模式 — 内联可编辑表格 -->
                    <template v-if="f.field_name === 'steps' && editingField === f.field_name">
                      <el-table :data="editSteps" border size="small" class="mini-step-table edit-step-table">
                        <el-table-column label="#" width="40">
                          <template #default="{ $index }">{{ $index + 1 }}</template>
                        </el-table-column>
                        <el-table-column label="操作步骤" min-width="180">
                          <template #default="{ $index }">
                            <el-input v-model="editSteps[$index].action" type="textarea" size="small" :autosize="{ minRows: 3 }" placeholder="操作步骤" />
                          </template>
                        </el-table-column>
                        <el-table-column label="预期结果" min-width="180">
                          <template #default="{ $index }">
                            <el-input v-model="editSteps[$index].expected" type="textarea" size="small" :autosize="{ minRows: 3 }" placeholder="预期结果" />
                          </template>
                        </el-table-column>
                        <el-table-column label="操作" width="50" fixed="right" align="center">
                          <template #default="{ $index }">
                            <div class="step-op-btns">
                              <el-button size="small" text type="danger" icon="Delete" title="删除" @click="removeStepAt($index)" />
                              <el-button size="small" text type="primary" icon="Plus" title="加行" @click="addStepBelow($index)" />
                            </div>
                          </template>
                        </el-table-column>
                      </el-table>
                      <div class="editor-actions">
                        <el-button size="small" type="primary" @click="saveManualEdit(f.field_name)">保存</el-button>
                        <el-button size="small" @click="cancelEdit">取消</el-button>
                      </div>
                    </template>
                    <!-- 步骤字段：只读模式 -->
                    <template v-else-if="f.field_name === 'steps' && (f.suggested || []).length">
                      <el-table
                        :data="f.suggested"
                        border
                        size="small"
                        class="mini-step-table"
                      >
                        <el-table-column prop="step_no" label="#" width="40" />
                        <el-table-column prop="action" label="操作步骤" min-width="120" />
                        <el-table-column prop="expected" label="预期结果" min-width="120" />
                      </el-table>
                    </template>
                    <span v-else-if="f.has_suggestion" class="suggested-text">{{ displayVal(f.suggested) }}</span>
                    <span v-else class="no-suggestion">—</span>
                  </template>
                </div>

                <div class="suggestion-actions">
                  <template v-if="f.has_suggestion && !fieldStates[f.field_name]">
                    <el-button size="small" type="primary" @click="acceptField(f.field_name)">采纳</el-button>
                    <el-button size="small" type="primary" plain @click="startEdit(f)">修改</el-button>
                    <el-button size="small" type="info" plain @click="ignoreField(f.field_name)">忽略</el-button>
                  </template>
                  <template v-if="fieldStates[f.field_name]">
                    <el-button size="small" type="info" plain @click="resetField(f.field_name)">重置</el-button>
                  </template>
                </div>

                <!-- 编辑区域（仅非步骤字段使用，步骤字段已内联编辑） -->
                <div v-if="editingField === f.field_name && f.field_name !== 'steps'" class="suggestion-editor">
                  <el-input
                    v-model="editDraft[f.field_name]"
                    type="textarea"
                    :rows="3"
                    size="small"
                    placeholder="请输入修改后的内容..."
                  />
                  <div class="editor-actions">
                    <el-button size="small" type="primary" @click="saveManualEdit(f.field_name)">保存</el-button>
                    <el-button size="small" @click="cancelEdit">取消</el-button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 底部提交 -->
            <div class="right-footer">
              <el-button size="small" @click="goBack">返回</el-button>
              <el-button size="small" type="primary" @click="submitReview" :loading="submitting" :disabled="!canSubmit">
                提交审核（{{ processedCount }}/{{ failCount }}）
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 原始输出弹窗 -->
    <el-dialog v-model="rawVisible" title="AI 原始输出" width="700px" destroy-on-close>
      <div class="raw-header">
        <span class="text-sm font-bold">{{ caseNumber }}</span>
        <el-button size="small" text @click="copyRawOutput">复制</el-button>
      </div>
      <pre class="raw-json">{{ rawFormatted }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useTagsViewStore } from "@/stores/tags-view";
import { ElMessage } from "element-plus";
import { CircleCheck } from "@element-plus/icons-vue";
import TaskAPI from "@/api/aitc/task";
import type { CaseVO } from "@/api/aitc/case";
import type { TaskItemVO, FieldSuggestionVO } from "@/api/aitc/task";
import { importanceLabel, scoreTag } from "../../constants";
import { ConfirmStatusEnum } from "@/enums/aitc";
import { useCaseReview, FIELD_LABEL_MAP, CASE_FIELD_ORDER, displayVal, type FieldItem } from "../shared/composables/useCaseReview";

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

const {
  fieldStates, manualValues, editingField, editDraft, editSteps,
  clearFieldStates, useFieldStats,
  acceptField, ignoreField, resetField, acceptAll, ignoreAll,
  startEdit, cancelEdit, saveManualEdit: _saveManualEdit,
  removeStepAt, addStepBelow,
  buildFields,
} = useCaseReview();

const rawVisible = ref(false);

const aiOutput = computed(() => itemData.value?.output as Record<string, any> | null);

// ── 左侧：原始用例详情（直接从 caseData 取，与 AI 无关） ──
const caseFields = computed(() => {
  if (!caseData.value) return [];
  return CASE_FIELD_ORDER.map(({ key, label }) => ({
    key,
    label,
    value: key === 'name'
      ? caseNumber.value
      : key === 'steps'
        ? (caseData.value!.steps || [])
        : (caseData.value as any)[key],
  }));
});

// ── 右侧：AI 审核字段（来源 AI 输出） ──
const aiFields = computed(() => {
  const raw = aiOutput.value?.fields;
  if (!Array.isArray(raw)) return [];
  return raw.map((f: any) => {
    const fn = f.field_name || "";
    const conclusion = f.conclusion || "pass";
    const has = conclusion === "fail" && f.suggested_value != null && String(f.suggested_value) !== "null" && String(f.suggested_value) !== "";
    const original = getOriginalValue(fn);
    return {
      field_name: fn,
      conclusion,
      rule_violated: f.rule_violated || "",
      suggested: f.suggested_value ?? null,
      original,
      has_suggestion: has,
    };
  });
});

const failFields = computed(() => aiFields.value.filter(f => f.conclusion === "fail"));
const passFields = computed(() => aiFields.value.filter(f => f.conclusion === "pass"));
const passCount = computed(() => passFields.value.length);

function getOriginalValue(fieldName: string): any {
  if (!caseData.value) return "";
  if (fieldName === "steps") return caseData.value.steps || [];
  return (caseData.value as any)[fieldName] || "";
}

const manualSteps = ref<any[]>([]);
const { failCount, processedCount, canSubmit } = useFieldStats(() =>
  failFields.value.map(f => ({ field_name: f.field_name, conclusion: f.conclusion }))
);

const fieldLabelMap = FIELD_LABEL_MAP;

const caseNumber = computed(() => {
  if (!caseData.value) return '';
  const prefix = caseData.value.project_prefix || '';
  const extId = caseData.value.external_id || '';
  const name = caseData.value.name || '';
  return `${prefix}${extId}__${name}`;
});

function saveManualEdit(fieldName: string) {
  _saveManualEdit(fieldName);
  if (fieldName === 'steps' && Array.isArray(manualValues.steps)) {
    manualSteps.value = [...manualValues.steps as any[]];
  }
}

const currentIndex = computed(() => allItems.value.findIndex(it => String(it.id) === itemId));
const hasPrev = computed(() => currentIndex.value > 0);
const hasNext = computed(() => currentIndex.value < allItems.value.length - 1);

const rawOutput = computed(() => itemData.value?.output);
const rawFormatted = computed(() => {
  try {
    return JSON.stringify(rawOutput.value, null, 2);
  } catch {
    return "";
  }
});

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
  router.replace(`/aitc/tasks/${taskId}/case-review/${prev.id}`);
  loadItem(String(prev.id));
}

function nextItem() {
  if (!hasNext.value) return;
  const next = allItems.value[currentIndex.value + 1];
  router.replace(`/aitc/tasks/${taskId}/case-review/${next.id}`);
  loadItem(String(next.id));
}

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
    clearFieldStates();
    manualSteps.value = [];
  } catch (e: any) {
    ElMessage.error(e?.message || "数据加载失败");
  } finally {
    loading.value = false;
  }
}

async function submitReview() {
  if (failCount.value > 0 && processedCount.value < failCount.value) {
    ElMessage.warning(`还有 ${failCount.value - processedCount.value} 个不合格字段未处理`);
    return;
  }
  if (!itemData.value) {
    ElMessage.warning("没有可审核的内容");
    return;
  }

  submitting.value = true;
  try {
    const fields = buildFields(failFields.value.map(f => ({
      field_name: f.field_name,
      conclusion: f.conclusion,
    })));

    const hasAccepted = fields.some(f => f.action === 'accept' || f.action === 'edit_accept');
    await TaskAPI.reviewItem(taskId, String(itemData.value.id), {
      task_id: taskId,
      item_id: String(itemData.value.id),
      confirm_status: hasAccepted ? ConfirmStatusEnum.ACCEPTED : ConfirmStatusEnum.IGNORED,
      fields,
    });

    ElMessage.success("审核成功，结果已保存");
    if (hasNext.value) {
      nextItem();
    } else {
      goBack();
    }
  } catch (e: any) {
    ElMessage.error(e?.message || "审核失败");
  } finally {
    submitting.value = false;
  }
}

// 全部采纳/全部忽略 包装函数
function doAcceptAll() {
  acceptAll(failFields.value);
}
function doIgnoreAll() {
  ignoreAll(failFields.value);
}

function showRawDialog() {
  rawVisible.value = true;
}

async function copyRawOutput() {
  try {
    await navigator.clipboard.writeText(rawFormatted.value);
    ElMessage.success("已复制到剪贴板");
  } catch {
    ElMessage.warning("复制失败，请手动复制");
  }
}

import { watch } from "vue";
watch(() => route.params.itemId, (newId) => {
  if (newId) loadItem(String(newId));
});

onMounted(() => loadItem());
</script>

<style scoped>
/* ==================== 顶部导航（紧凑单行） ==================== */
.header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  padding: 6px 10px;
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 4px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}
.header-center {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  color: #909399;
}
.page-title {
  font-size: 13px;
  font-weight: 700;
  color: #303133;
}
.case-name {
  font-size: 11px;
  color: #909399;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 4px;
}
.count-text {
  font-size: 12px;
  color: #909399;
}
.stat-pass { color: #67c23a; font-weight: 600; font-size: 12px; }
.stat-fail { color: #f56c6c; font-weight: 600; font-size: 12px; }
.stat-divider { color: #dcdfe6; font-size: 12px; }
.stat-processed { color: #909399; font-size: 11px; }

/* ==================== 页面整体 ==================== */
.case-review-page {
  padding: 6px 10px;
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
}

/* ==================== 主体区域：左右两个大框 ==================== */
.main-body {
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.empty-wrapper {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.two-panel {
  display: flex;
  gap: 8px;
  height: 100%;
  min-height: 0;
}

.panel {
  flex: 1;
  min-width: 0;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
  flex-shrink: 0;
}
.panel-title {
  font-size: 13px;
  font-weight: 700;
  color: #303133;
}
.panel-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
}
.badge-pass-bg { background: #f0f9eb; color: #67c23a; border: 1px solid #e1f3d8; }
.badge-fail-bg { background: #fef0f0; color: #f56c6c; border: 1px solid #fde2e2; }

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  min-height: 0;
}

/* ==================== 左侧：用例详情表格 ==================== */
.detail-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  border: 1px solid #ebeef5;
}
.detail-table tr {
  border-bottom: 1px solid #ebeef5;
}
.detail-table tr:last-child {
  border-bottom: none;
}
.detail-label {
  width: 90px;
  padding: 7px 10px;
  background: #fafafa;
  color: #606266;
  font-weight: 600;
  font-size: 12px;
  vertical-align: top;
  border-right: 1px solid #ebeef5;
}
.detail-value {
  padding: 7px 10px;
  color: #303133;
  font-size: 12px;
  line-height: 1.55;
  vertical-align: top;
  word-break: break-all;
}

/* ==================== 右侧：评分卡片 ==================== */
.score-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 10px;
}
.score-ring {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: conic-gradient(#409eff 0% 80%, #e4e7ed 80% 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #303133;
  position: relative;
}
.score-ring::after {
  content: '';
  position: absolute;
  width: 40px;
  height: 40px;
  background: #fff;
  border-radius: 50%;
}
.score-num {
  font-size: 17px;
  font-weight: 700;
  z-index: 1;
}
.score-unit {
  font-size: 10px;
  color: #909399;
  z-index: 1;
}
.score-info {
  flex: 1;
  min-width: 0;
}
.score-label {
  font-size: 12px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}
.score-assessment {
  font-size: 11px;
  color: #606266;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ==================== 建议列表 ==================== */
.suggestions-list {
  margin-bottom: 10px;
}
.box-title {
  font-size: 12px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 6px;
}
.all-pass-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
  border-radius: 6px;
  color: #67c23a;
  font-size: 12px;
}

.suggestion-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  margin-bottom: 8px;
  overflow: hidden;
  transition: all 0.2s;
}
.suggestion-card.suggestion-accepted { border-left: 3px solid #409eff; }
.suggestion-card.suggestion-ignored { border-left: 3px solid #c0c4cc; opacity: 0.75; }
.suggestion-card.suggestion-manual { border-left: 3px solid #e6a23c; }
.suggestion-card:not(.suggestion-accepted):not(.suggestion-ignored):not(.suggestion-manual) {
  border-left: 3px solid #f56c6c;
}

.suggestion-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 10px;
  background: #fafafa;
  border-bottom: 1px solid #ebeef5;
}
.suggestion-field {
  font-size: 13px;
  font-weight: 700;
  color: #303133;
}
.suggestion-badges {
  display: flex;
  gap: 4px;
}

.reason-row {
  padding: 5px 10px;
  background: #fdf6ec;
  font-size: 11px;
  border-bottom: 1px solid #ebeef5;
}
.suggestion-accepted .reason-row { background: #ecf5ff; }
.reason-label {
  font-weight: 600;
  color: #e6a23c;
}
.suggestion-accepted .reason-label { color: #409eff; }
.reason-text {
  color: #606266;
}

.suggestion-value {
  padding: 8px 10px;
  font-size: 12px;
  color: #303133;
  line-height: 1.55;
  word-break: break-all;
}
.ignored-tip {
  color: #909399;
  font-style: italic;
}
.suggested-text {
  color: #409eff;
  font-weight: 500;
}
.no-suggestion {
  color: #c0c4cc;
}
.empty-text {
  color: #c0c4cc;
  font-style: italic;
}

.suggestion-actions {
  display: flex;
  gap: 4px;
  padding: 0 10px 8px 10px;
  flex-wrap: wrap;
}

.suggestion-editor {
  padding: 8px 10px;
  border-top: 1px solid #ebeef5;
  background: #fafbfc;
}

/* ==================== 公共 Badge 标签 ==================== */
.badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
}
.badge-pass { background: #f0f9eb; color: #67c23a; border: 1px solid #e1f3d8; }
.badge-fail { background: #fef0f0; color: #f56c6c; border: 1px solid #fde2e2; }
.badge-state-accept { background: #ecf5ff; color: #409eff; border: 1px solid #d9ecff; }
.badge-state-ignore { background: #f5f7fa; color: #909399; border: 1px solid #e4e7ed; }
.badge-state-manual { background: #fdf6ec; color: #e6a23c; border: 1px solid #faecd8; }

/* ==================== 编辑区域公共样式 ==================== */
.editor-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.step-op-btns {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.step-op-btns .el-button {
  padding: 0;
  min-height: 22px;
  height: 22px;
}

/* ==================== 迷你步骤表 ==================== */
.mini-step-table {
  font-size: 11px;
}
.mini-step-table :deep(th) {
  font-size: 10px;
  padding: 2px 4px !important;
  background: #f5f7fa !important;
}
.mini-step-table :deep(td) {
  font-size: 11px;
  padding: 2px 4px !important;
}
.mini-step-table :deep(.cell) {
  padding: 0 2px !important;
  line-height: 1.4;
}

/* ==================== 右侧底部提交 ==================== */
.right-footer {
  display: flex;
  justify-content: center;
  gap: 8px;
  padding-top: 6px;
  border-top: 1px solid #ebeef5;
}

/* ==================== 原始输出弹窗 ==================== */
.raw-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}
.raw-json {
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
