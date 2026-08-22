/**
 * 用例类型定义
 */

import type { BaseQueryParams } from "@/api/common";

export interface CaseStep {
  step_no: number;
  action: string;
  expected: string;
}

export interface CaseQueryParams extends BaseQueryParams {
  projectId?: string;
  suiteId?: string;
  isCore?: number;
  isSample?: number;
  reviewStatus?: number;
  importance?: number;
  keywords?: string;
  sortField?: string;
  sortOrder?: string;
}

export interface CaseVO {
  id: string;
  project_id: string;
  project_prefix: string;
  suite_id: string;
  suite_name: string;
  external_id?: string;
  name: string;
  purpose?: string;
  summary?: string;
  preconditions?: string;
  topo?: string;
  test_data?: string;
  steps: CaseStep[];
  // TestLink 原文（HTML 富文本）
  summary_raw?: string;
  preconditions_raw?: string;
  steps_raw?: string;
  test_data_raw?: string;
  steps_parse_status?: number;
  importance: number;
  is_core: number;
  core_reason?: string;
  core_source?: number;
  is_sample: number;
  review_status: number;
  script_count: number;
  create_time?: string;
  update_time?: string;
}

export interface CaseForm {
  external_id?: string;
  name: string;
  purpose?: string;
  summary?: string;
  preconditions?: string;
  topo?: string;
  test_data?: string;
  steps: CaseStep[];
  // TestLink 原文（HTML 富文本）
  summary_raw?: string;
  preconditions_raw?: string;
  steps_raw?: string;
  test_data_raw?: string;
  steps_parse_status?: number;
  importance: number;
}

export interface CaseCoreMark {
  case_id: string;
  is_core: number;
  reason?: string;
}

export interface CaseSampleMark {
  case_id: string;
  is_sample: number;
}

export interface ImportResult {
  created: number;
  updated: number;
  errors: { row: number; msg: string }[];
}
