import { useWindowSize } from "@vueuse/core";
import { useAppStore } from "@/stores";
import { DeviceEnum } from "@/enums/settings";

const MOBILE_BREAKPOINT = 768;

/**
 * 根据窗口宽度同步设备类型和侧边栏展开状态
 *
 * - ≥992px：桌面宽屏，默认保持侧边栏隐藏，由用户点顶部图标决定是否展开（不自动打开）
 * - 768~992px：桌面窄屏，侧边栏保持隐藏
 * - <768px：移动端，侧边栏强制隐藏
 */
export function useLayoutDevice() {
  const appStore = useAppStore();
  const { width } = useWindowSize();

  const isDesktop = computed(() => width.value >= MOBILE_BREAKPOINT);

  watchEffect(() => {
    const device = isDesktop.value ? DeviceEnum.DESKTOP : DeviceEnum.MOBILE;

    appStore.toggleDevice(device);

    // 移动端强制隐藏侧边栏；桌面端不干预用户手动展开/收起状态
    if (!isDesktop.value) {
      appStore.closeSidebar();
    }
  });

  return {
    isDesktop,
  };
}
