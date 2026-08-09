/**
 * 审核路由跳转工具
 * 统一入口，消除 index.vue / detail.vue / case_review / script_gen 中的重复跳转逻辑
 */
import type { Router } from "vue-router"
import type { TaskItemVO } from "@/api/aitc/task"
import { ItemStatusEnum } from "@/enums/aitc"

/** 根据任务类型推断审核页路径 */
export function resolveReviewPath(taskType: string, taskId: string, itemId: string): string {
  if (taskType === "case_review") {
    return `/aitc/tasks/${taskId}/case-review/${itemId}`
  }
  if (taskType === "case_complete") {
    return `/aitc/tasks/${taskId}/case-complete/${itemId}`
  }
  if (taskType === "script_gen") {
    return `/aitc/tasks/${taskId}/script-review/${itemId}`
  }
  if (taskType === "core_select") {
    return `/aitc/tasks/${taskId}/core-review`
  }
  // 未知类型回退到详情页
  return `/aitc/tasks/${taskId}`
}

/** 导航到任务下第一个可审核的子项，若无则回退到详情页 */
export async function navigateToReview(
  router: Router,
  taskType: string,
  taskId: string,
  items: TaskItemVO[],
) {
  const successItems = items.filter(i => i.item_status === ItemStatusEnum.SUCCESS)
  if (successItems.length > 0) {
    const path = resolveReviewPath(taskType, taskId, String(successItems[0].id))
    router.push(path)
  } else {
    router.push(`/aitc/tasks/${taskId}`)
  }
}
