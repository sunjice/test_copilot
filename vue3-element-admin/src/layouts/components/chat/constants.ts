/** Chat 相关静态常量 */

/** 工具名 → 中文进度提示 */
export const TOOL_LABELS: Record<string, string> = {
  list_projects: "正在获取项目列表...",
  get_suite_tree: "正在加载模块结构...",
  search_cases: "正在搜索用例...",
  get_case_detail: "正在查看用例详情...",
  get_suite_samples: "正在获取样本用例...",
  create_core_select_task: "正在准备核心用例挑选任务...",
  create_case_review_task: "正在准备用例审核任务...",
  create_script_gen_task: "正在准备脚本生成任务...",
  create_case_complete_task: "正在准备完善用例任务...",
  complete_case_steps: "正在补写测试步骤...",
  design_test_case: "正在设计测试用例...",
}

export function toolLabel(name: string): string {
  return TOOL_LABELS[name] || "处理中..."
}
