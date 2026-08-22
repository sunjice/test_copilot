/** AI 对话 — 页面上下文共享 Store。
 *
 * 各页面在 onMounted 时调用 register() 注册当前页面类型（及其所属 domain），
 * 在项目/模块/用例选择变化时调用 update() 更新上下文数据。
 *
 * AI 对话框发消息前从此 Store 读取上下文，同步到后端会话。
 *
 * 多域化改造：上下文按 domain 分区软隔离，每个域独立维护自己的上下文桶，
 * 切域时自动切换 activeDomain，互不干扰。
 *
 * ======== 使用示例 ========
 *
 * // 用例管理页（case 域）
 * aiContextStore.register("case", "case")
 * aiContextStore.update({ projectId: 1, suiteId: 5, selectedCaseIds: [101,102], currentCaseId: 101 })
 *
 * // 脚本管理页（case 域）
 * aiContextStore.register("script", "case")
 * aiContextStore.update({ projectId: 1, scriptId: 42 })
 *
 * // 知识库问答页（kb 域）
 * aiContextStore.register("kb", "kb")
 *
 * // 任意页面离开时清理
 * onUnmounted(() => aiContextStore.unregister())
 */

import { ref, computed } from "vue";
import { defineStore } from "pinia";

/** 驼峰转下划线 */
function toSnake(key: string): string {
  return key.replace(/([A-Z])/g, "_$1").toLowerCase();
}

/** 判断值是否 "有内容"（非 null/undefined/空字符串/空数组） */
function isPresent(v: any): boolean {
  if (v == null) return false;
  if (v === "") return false;
  if (Array.isArray(v) && v.length === 0) return false;
  return true;
}

export interface AiPageContext {
  currentPage: string;
  projectId?: number | null;
  /** 以下为各页面按需设置的字段，驼峰自动转下划线 */
  [key: string]: any;
}

/** 空上下文桶工厂 */
function emptyBucket(): AiPageContext {
  return { currentPage: "", projectId: null };
}

export const useAiContextStore = defineStore("aiContext", () => {
  /** 按域分区上下文：domain → AiPageContext */
  const contextByDomain = ref<Record<string, AiPageContext>>({});
  /** 当前激活的域（默认 case，兼容旧调用） */
  const activeDomain = ref("case");

  /** 当前激活域的上下文桶（只读便捷访问） */
  const context = computed<AiPageContext>(
    () => contextByDomain.value[activeDomain.value] ?? emptyBucket()
  );

  /** 序列化为后端 context_json 格式（驼峰 → 下划线），只取当前激活域 */
  const contextJson = computed(() => {
    const result: Record<string, any> = {};
    const bucket = contextByDomain.value[activeDomain.value] ?? emptyBucket();
    // current_page 始终携带（空字符串也传，便于后端判断页面准入）
    result["current_page"] = bucket.currentPage || "";
    for (const [key, val] of Object.entries(bucket)) {
      if (key === "currentPage") continue;
      if (isPresent(val)) {
        result[toSnake(key)] = val;
      }
    }
    // 显式携带 selected_case_ids / current_case_id，即便为空也要通知后端清除旧值
    if (!("selected_case_ids" in result)) {
      result["selected_case_ids"] = [];
    }
    if (!("current_case_id" in result)) {
      result["current_case_id"] = null;
    }
    return result;
  });

  /** 注册当前页面（可选指定 domain，缺省 "case"） */
  function register(page: string, domain: string = "case") {
    activeDomain.value = domain;
    const bucket = contextByDomain.value[domain] ?? emptyBucket();
    bucket.currentPage = page;
    contextByDomain.value[domain] = bucket;
  }

  /** 切换激活域（不改变该域已有内容） */
  function setDomain(domain: string) {
    activeDomain.value = domain;
  }

  /** 合并更新上下文数据（任意字段，驼峰命名，自动转下划线），只写当前激活域 */
  function update(data: Record<string, any>) {
    const d = activeDomain.value;
    const bucket = contextByDomain.value[d] ?? emptyBucket();
    contextByDomain.value[d] = { ...bucket, ...data };
  }

  /** 取消注册（页面 onUnmounted 时调用，只清当前域页面数据保留 projectId） */
  function unregister() {
    const d = activeDomain.value;
    const bucket = contextByDomain.value[d] ?? emptyBucket();
    const pid = bucket.projectId;
    contextByDomain.value[d] = { currentPage: "", projectId: pid } as AiPageContext;
  }

  /** 清空全部上下文（会话切换时调用，只清当前域） */
  function clear() {
    contextByDomain.value[activeDomain.value] = emptyBucket();
  }

  return {
    context,
    contextByDomain,
    activeDomain,
    contextJson,
    register,
    setDomain,
    update,
    unregister,
    clear,
  };
});
