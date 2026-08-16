<template>
  <div class="layout-root" :class="layoutClass">
    <div
      v-if="showOverlay && isSidebarOpen && (isMobile || desktopOverlay)"
      class="layout-root__overlay"
      @click="closeSidebar"
    />

    <slot />
  </div>
</template>

<script setup lang="ts">
import { useLayout } from "./composables/useLayout";

withDefaults(
  defineProps<{
    /** 展开侧边栏时是否显示遮罩层（移动端始终显示；桌面端由 desktopOverlay 控制，LeftLayout 需要，MixLayout 不需要） */
    showOverlay?: boolean;
    /** 桌面端展开侧边栏时是否也显示遮罩层（抽屉式布局需要） */
    desktopOverlay?: boolean;
  }>(),
  {
    showOverlay: true,
    desktopOverlay: false,
  }
);

const { layoutClass, isSidebarOpen, isMobile, closeSidebar } = useLayout();
</script>

<style lang="scss" scoped>
.layout-root {
  width: 100%;
  height: 100%;

  &__overlay {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 999;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.3);
  }
}
</style>
