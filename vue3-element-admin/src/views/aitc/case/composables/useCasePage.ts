import { ref, reactive, onMounted, onUnmounted, watch, nextTick } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadProps } from "element-plus";
import ProjectAPI from "@/api/aitc/project";
import SuiteAPI from "@/api/aitc/suite";
import CaseAPI from "@/api/aitc/case";
import { useAiContextStore } from "@/stores/aiContext";
import { CaseImportanceEnum, CoreSourceEnum } from "@/enums/aitc";
import type { OptionItem, PageResult } from "@/api/common";
import type { CaseVO, CaseQueryParams, CaseForm, ImportResult } from "@/api/aitc/case";

interface StepForm {
  step_no: number;
  action: string;
  expected: string;
}

/**
 * 用例页核心逻辑编排：项目/套件树/表格/详情/编辑/导入/aiContext
 */
export function useCasePage() {
  // ── 项目 ──
  const selectedProjectId = ref("");
  const selectedProjectName = ref("");
  const sidebarCollapsed = ref(false);
  const projectOptions = ref<OptionItem[]>([]);

  async function loadProjectOptions() {
    const res = await ProjectAPI.getOptions();
    projectOptions.value = res || [];
    _syncProjectName();
  }

  function _syncProjectName() {
    const id = selectedProjectId.value;
    if (!id) {
      selectedProjectName.value = "";
      return;
    }
    const found = projectOptions.value.find((p) => String(p.value) === String(id));
    selectedProjectName.value = found?.label || "";
  }

  // ── 套件树状态 ──
  const selectedSuiteId = ref("");
  const selectedSuiteName = ref("");
  const currentCaseId = ref<number | null>(null);

  function onProjectChange() {
    selectedSuiteId.value = "";
    selectedSuiteName.value = "";
    queryParams.suiteId = undefined;
    viewMode.value = "table";
    viewingCase.value = null;
    tableData.value = [];
    total.value = 0;
    selectedIds.value = [];
    currentCaseId.value = null;
    _syncProjectName();
  }

  function onTreeClick(node: any) {
    if (node.node_type === "case") {
      _snapshotSelectedIds = [...selectedIds.value];
      const caseId = Number(-(node.id as number));
      CaseAPI.getById(String(caseId)).then((res) => {
        viewingCase.value = res as CaseVO;
        viewMode.value = "detail";
      });
      if (node.parent_id != null) {
        const parentId = String(node.parent_id);
        if (selectedSuiteId.value !== parentId) {
          selectedSuiteId.value = parentId;
          selectedSuiteName.value = ""; // 用例节点不保存模块名
        }
      }
      currentCaseId.value = caseId;
      return;
    }
    selectedSuiteId.value = String(node.id);
    selectedSuiteName.value = node.label || node.name || "";
    queryParams.suiteId = String(node.id) as any;
    viewMode.value = "table";
    selectedIds.value = [];
    currentCaseId.value = null;
    loadCases();
  }

  /** 从详情视图返回表格视图 */
  async function backToTable() {
    viewMode.value = "table";
    viewingCase.value = null;
    currentCaseId.value = null;
    await nextTick();
    if (_snapshotSelectedIds.length && tableRef.value && tableData.value.length) {
      for (const row of tableData.value) {
        if (_snapshotSelectedIds.includes(row.id)) {
          tableRef.value.toggleRowSelection(row, true);
        }
      }
    }
  }

  // ── 用例列表 ──
  const tableData = ref<CaseVO[]>([]);
  const loading = ref(false);
  const total = ref(0);
  const tableRef = ref();
  const selectedIds = ref<(string | number)[]>([]);
  let _snapshotSelectedIds: (string | number)[] = [];

  function handleSelectionChange(ids: (string | number)[]) {
    selectedIds.value = ids;
  }

  const queryParams = reactive<CaseQueryParams>({
    pageNum: 1, pageSize: 100,
    projectId: undefined, suiteId: undefined,
    isCore: undefined, reviewStatus: undefined,
    importance: undefined, keywords: undefined,
  });

  function onSortChange({ prop, order }: { prop: string; order: string | null }) {
    queryParams.sortField = order ? prop : undefined;
    queryParams.sortOrder = order || undefined;
    loadCases();
  }

  async function loadCases() {
    if (!selectedProjectId.value) return;
    loading.value = true;
    try {
      queryParams.projectId = selectedProjectId.value;
      const res = await CaseAPI.getPage(queryParams);
      const page = res as PageResult<CaseVO>;
      tableData.value = page?.list || (res as any)?.records || [];
      total.value = page?.total || (res as any)?.total || 0;
    } finally {
      loading.value = false;
    }
  }

  function handleReset() {
    queryParams.isCore = undefined;
    queryParams.isSample = undefined;
    queryParams.reviewStatus = undefined;
    queryParams.importance = undefined;
    queryParams.keywords = undefined;
    queryParams.pageNum = 1;
    viewMode.value = "table";
    viewingCase.value = null;
    loadCases();
  }

  // ── 核心/样本标记 ──
  async function toggleCore(row: CaseVO) {
    const newVal = row.is_core ? 0 : 1;
    try {
      await ElMessageBox.confirm(`确定${newVal ? "标记为核心用例" : "取消核心用例"}？`, "操作确认");
      const updated = await CaseAPI.markCore({ case_id: String(row.id), is_core: newVal });
      ElMessage.success("操作成功");
      row.is_core = newVal;
      row.core_reason = (updated as any)?.core_reason ?? row.core_reason;
      row.core_source = (updated as any)?.core_source ?? (newVal ? CoreSourceEnum.MANUAL : undefined);
    } catch { /* cancelled */ }
  }

  async function toggleSample(row: CaseVO) {
    const newVal = row.is_sample ? 0 : 1;
    try {
      await CaseAPI.markSample({ case_id: String(row.id), is_sample: newVal });
      ElMessage.success(newVal ? "已标记为样本用例" : "已取消样本用例");
      row.is_sample = newVal;
    } catch { /* cancelled */ }
  }

  // ── 右侧视图模式 ──
  const viewMode = ref<"table" | "detail">("table");
  const viewingCase = ref<CaseVO | null>(null);

  async function showDetail(row: CaseVO) {
    _snapshotSelectedIds = [...selectedIds.value];
    const res = await CaseAPI.getById(String(row.id));
    viewingCase.value = res as CaseVO;
    viewMode.value = "detail";
    currentCaseId.value = Number(row.id);
  }

  // ── 用例编辑 ──
  const isEditing = ref(false);
  const editSubmitting = ref(false);
  const editingCaseId = ref<string>("");

  const editForm = reactive<{
    external_id: string;
    name: string;
    purpose: string;
    summary: string;
    preconditions: string;
    topo: string;
    test_data: string;
    steps: StepForm[];
    importance: number;
  }>({
    external_id: "", name: "", purpose: "", summary: "", preconditions: "", topo: "", test_data: "",
    steps: [], importance: CaseImportanceEnum.MEDIUM,
  });

  async function openEdit(row: CaseVO) {
    _snapshotSelectedIds = [...selectedIds.value];
    const res = await CaseAPI.getById(String(row.id));
    viewingCase.value = res as CaseVO;
    viewMode.value = "detail";
    currentCaseId.value = Number(row.id);
    populateEditForm(res as CaseVO);
    isEditing.value = true;
  }

  function startEdit(row: CaseVO) {
    populateEditForm(row);
    isEditing.value = true;
  }

  function populateEditForm(row: CaseVO) {
    editingCaseId.value = String(row.id);
    editForm.external_id = row.external_id || "";
    editForm.name = row.name;
    editForm.purpose = row.purpose || "";
    editForm.summary = row.summary || "";
    editForm.preconditions = row.preconditions || "";
    editForm.topo = row.topo || "";
    editForm.test_data = row.test_data || "";
    editForm.importance = row.importance;
    editForm.steps = (row.steps || []).map((s, i) => ({
      step_no: i + 1, action: s.action, expected: s.expected,
    }));
  }

  async function cancelEdit() {
    try {
      await ElMessageBox.confirm("取消后未保存的修改将丢失，确定取消？", "提示", {
        confirmButtonText: "确定取消", cancelButtonText: "继续编辑", type: "warning",
      });
      isEditing.value = false;
    } catch { /* 用户点击继续编辑 */ }
  }

  function addStep() {
    editForm.steps.push({ step_no: editForm.steps.length + 1, action: "", expected: "" });
  }

  function removeStep(index: number) {
    editForm.steps.splice(index, 1);
    editForm.steps.forEach((s, i) => (s.step_no = i + 1));
  }

  async function submitEdit(treeRef?: any) {
    if (!editForm.name.trim()) {
      ElMessage.warning("请输入用例名称");
      return;
    }
    editSubmitting.value = true;
    try {
      const data: CaseForm = {
        external_id: editForm.external_id || undefined,
        name: editForm.name,
        purpose: editForm.purpose || undefined,
        summary: editForm.summary || undefined,
        preconditions: editForm.preconditions || undefined,
        topo: editForm.topo || undefined,
        test_data: editForm.test_data || undefined,
        steps: editForm.steps.map((s, i) => ({ step_no: i + 1, action: s.action, expected: s.expected })),
        importance: editForm.importance,
      };
      await CaseAPI.update(editingCaseId.value, data);
      ElMessage.success("保存成功");
      isEditing.value = false;

      if (viewMode.value === "detail" && viewingCase.value) {
        const res = await CaseAPI.getById(editingCaseId.value);
        viewingCase.value = res as CaseVO;
      }
      loadCases();

      // 更新树节点
      if (treeRef?.updateCaseNode) {
        treeRef.updateCaseNode(Number(editingCaseId.value), {
          external_id: editForm.external_id || undefined,
          name: editForm.name,
          purpose: editForm.purpose || undefined,
        });
      }
    } finally {
      editSubmitting.value = false;
    }
  }

  // ── Excel 导入 ──
  const showImportResult = ref(false);
  const importResult = reactive<ImportResult>({ created: 0, updated: 0, errors: [] });

  async function downloadTemplate() {
    const res = await CaseAPI.downloadTemplate();
    const blob = new Blob([res as any], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "用例导入模板.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  }

  const handleImport: UploadProps["beforeUpload"] = async (file) => {
    if (!selectedProjectId.value) { ElMessage.warning("请先选择项目"); return false; }
    try {
      const res = await CaseAPI.importExcel(selectedProjectId.value, file);
      Object.assign(importResult, res);
      showImportResult.value = true;
      loadCases();
      onProjectChange();
    } catch (e: any) {
      ElMessage.error(e?.message || "导入失败");
    }
    return false;
  };

  // ── AI 上下文 ──
  const aiContextStore = useAiContextStore();

  function initAiContext() {
    watch([selectedProjectId, selectedSuiteId, selectedIds, currentCaseId, selectedProjectName, selectedSuiteName], () => {
      aiContextStore.update({
        projectId: selectedProjectId.value ? Number(selectedProjectId.value) : null,
        projectName: selectedProjectName.value || null,
        suiteId: selectedSuiteId.value ? Number(selectedSuiteId.value) : null,
        suiteIds: selectedSuiteId.value ? [Number(selectedSuiteId.value)] : null,
        suiteName: selectedSuiteName.value || null,
        suiteNames: selectedSuiteName.value ? [selectedSuiteName.value] : null,
        selectedCaseIds: selectedIds.value.map((id) => Number(id)),
        currentCaseId: currentCaseId.value != null ? Number(currentCaseId.value) : null,
      });
    });
  }

  function mountAiContext() {
    aiContextStore.register("case");
  }

  function unmountAiContext() {
    aiContextStore.unregister();
  }

  return {
    // 项目
    selectedProjectId, sidebarCollapsed, projectOptions, loadProjectOptions,
    // 套件树
    selectedSuiteId, currentCaseId,
    onProjectChange, onTreeClick, backToTable,
    // 表格
    tableData, loading, total, tableRef, selectedIds, queryParams,
    handleSelectionChange, onSortChange, loadCases, handleReset,
    // 标记
    toggleCore, toggleSample,
    // 视图
    viewMode, viewingCase, showDetail,
    // 编辑
    isEditing, editSubmitting, editingCaseId, editForm,
    openEdit, startEdit, populateEditForm, cancelEdit, addStep, removeStep, submitEdit,
    // 导入
    showImportResult, importResult, downloadTemplate, handleImport,
    // aiContext
    initAiContext, mountAiContext, unmountAiContext,
  };
}
