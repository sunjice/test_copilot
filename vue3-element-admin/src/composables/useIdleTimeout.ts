import { onUnmounted, watch } from "vue";
import { useRoute } from "vue-router";
import { useUserStoreHook } from "@/stores/user";
import { redirectToLogin } from "@/utils/auth";
import { ElMessageBox } from "element-plus";

/** 默认闲置超时 15 分钟 */
const IDLE_TIMEOUT_MS = 900 * 1000;

/** 用户活动事件列表 */
const ACTIVITY_EVENTS = ["mousemove", "keydown", "mousedown", "touchstart", "scroll"] as const;

/**
 * 闲置超时自动登出
 *
 * 监听用户活动，超过指定时间无操作后提示并登出。
 * 只在已登录状态下生效。
 */
export function useIdleTimeout(timeoutMs: number = IDLE_TIMEOUT_MS) {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let isLoggedOut = false;

  const userStore = useUserStoreHook();
  const route = useRoute();

  /** 重置倒计时 */
  function resetTimer() {
    if (isLoggedOut) return;
    if (timer) clearTimeout(timer);
    timer = setTimeout(onTimeout, timeoutMs);
  }

  /** 超时处理 */
  async function onTimeout() {
    isLoggedOut = true;
    teardown();

    // 已在登录页则跳过
    if (route.path === "/login") return;

    await ElMessageBox.alert("您已长时间未操作，请重新登录", "登录已过期", {
      confirmButtonText: "确定",
      type: "warning",
      showClose: false,
      closeOnClickModal: false,
      closeOnPressEscape: false,
    });
    // 空闲超时场景 token 已过期，不能调用会发请求的 logout()（会命中 401 拦截器引发二次跳转）。
    // 直接清空本地状态，并通过统一的 redirectToLogin 软跳转登录页。
    await redirectToLogin("您已长时间未操作，请重新登录");
  }

  /** 绑定事件 */
  function setup() {
    ACTIVITY_EVENTS.forEach((event) => {
      window.addEventListener(event, resetTimer, { passive: true });
    });
    resetTimer();
  }

  /** 解绑事件并清定时器 */
  function teardown() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    ACTIVITY_EVENTS.forEach((event) => {
      window.removeEventListener(event, resetTimer);
    });
  }

  // 监听用户会话：有 userId 表示已登录，空表示已登出
  // 注意：不能用 isLoggedIn()，token 过期后它会返回 false 导致定时器被销毁
  const stopWatch = watch(
    () => userStore.userInfo.userId,
    (userId) => {
      if (userId) {
        isLoggedOut = false;
        setup();
      } else {
        isLoggedOut = true;
        teardown();
      }
    },
    { immediate: true }
  );

  onUnmounted(() => {
    stopWatch();
    teardown();
  });

  return { resetTimer, teardown };
}
