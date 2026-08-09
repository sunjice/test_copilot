import request from "@/utils/request";
import type {
  TaskCreateForm,
  TaskQueryParams,
  TaskVO,
  TaskItemVO,
  TaskConfirmReq,
  TaskDetail,
  ReviewRecordVO,
  ReviewItemReq,
  TaskItemWithCase,
  PendingSuiteNode,
  PendingCaseVO,
  CaseReviewDetailVO,
  CaseReviewReq,
} from "./types";
import type { PageResult } from "@/api/common";

const TASK_BASE_URL = "/api/v1/aitc/tasks";
const CASE_BASE_URL = "/api/v1/aitc/cases";

// ── AI 任务 ──

const TaskAPI = {
  create(data: TaskCreateForm) {
    return request<unknown, TaskVO>({
      url: `${TASK_BASE_URL}`,
      method: "post",
      data,
    });
  },

  getPage(params: TaskQueryParams) {
    return request<unknown, PageResult<TaskVO>>({
      url: `${TASK_BASE_URL}`,
      method: "get",
      params,
    });
  },

  getDetail(taskId: string) {
    return request<unknown, TaskDetail>({
      url: `${TASK_BASE_URL}/${taskId}`,
      method: "get",
    });
  },

  getItems(taskId: string) {
    return request<unknown, TaskItemVO[]>({
      url: `${TASK_BASE_URL}/${taskId}/items`,
      method: "get",
    });
  },

  getItemWithCase(taskId: string, itemId: string) {
    return request<unknown, TaskItemWithCase>({
      url: `${TASK_BASE_URL}/${taskId}/items/${itemId}`,
      method: "get",
    });
  },

  reviewItem(taskId: string, itemId: string, data: ReviewItemReq) {
    return request({
      url: `${TASK_BASE_URL}/${taskId}/items/${itemId}/review`,
      method: "post",
      data,
    });
  },

  getReviewRecords(taskId: string) {
    return request<unknown, ReviewRecordVO[]>({
      url: `${TASK_BASE_URL}/${taskId}/review-records`,
      method: "get",
    });
  },

  rerun(taskId: string) {
    return request({
      url: `${TASK_BASE_URL}/${taskId}/rerun`,
      method: "post",
    });
  },

  confirm(taskId: string, data: TaskConfirmReq) {
    return request({
      url: `${TASK_BASE_URL}/${taskId}/confirm`,
      method: "post",
      data,
    });
  },

  stop(taskId: string) {
    return request({
      url: `${TASK_BASE_URL}/${taskId}/stop`,
      method: "post",
    });
  },
};

export default TaskAPI;

// ── 审核工作台（归属任务域）──

const ReviewAPI = {
  getPendingTree(projectId: string) {
    return request<unknown, PendingSuiteNode[]>({
      url: `${CASE_BASE_URL}/pending-tree`,
      method: "get",
      params: { projectId },
    });
  },

  getPendingList(suiteId: string) {
    return request<unknown, PendingCaseVO[]>({
      url: `${CASE_BASE_URL}/pending-list`,
      method: "get",
      params: { suiteId },
    });
  },

  getReviewDetail(caseId: string) {
    return request<unknown, CaseReviewDetailVO>({
      url: `${CASE_BASE_URL}/${caseId}/review-detail`,
      method: "get",
    });
  },

  submitReview(caseId: string, data: CaseReviewReq) {
    return request({
      url: `${CASE_BASE_URL}/${caseId}/review`,
      method: "post",
      data,
    });
  },
};

export { ReviewAPI };

export * from "./types";
