import type { App } from "vue";
import { createRouter, createWebHashHistory, type RouteRecordRaw } from "vue-router";

export const Layout = () => import("@/layouts/index.vue");

// 静态路由
export const constantRoutes: RouteRecordRaw[] = [
  {
    path: "/redirect",
    component: Layout,
    meta: { hidden: true },
    children: [
      {
        path: "/redirect/:path(.*)",
        component: () => import("@/views/redirect.vue"),
      },
    ],
  },

  {
    path: "/login",
    component: () => import("@/views/login/index.vue"),
    meta: { hidden: true },
  },

  {
    path: "/",
    name: "/",
    component: Layout,
    redirect: "/dashboard",
    children: [
      {
        path: "dashboard",
        component: () => import("@/views/dashboard/index.vue"),
        // 用于 keep-alive 功能，需要与 SFC 中自动推导或显式声明的组件名称一致
        // 参考文档: https://cn.vuejs.org/guide/built-ins/keep-alive.html#include-exclude
        name: "Dashboard",
        meta: {
          title: "dashboard",
          icon: "homepage",
          affix: true,
          keepAlive: true,
        },
      },
      {
        path: "401",
        component: () => import("@/views/error/401.vue"),
        meta: { hidden: true },
      },
      {
        path: "404",
        component: () => import("@/views/error/404.vue"),
        meta: { hidden: true },
      },
      {
        path: "profile",
        name: "Profile",
        component: () => import("@/views/profile/index.vue"),
        meta: { title: "个人中心", icon: "user", hidden: true },
      },
      {
        path: "profile/notice",
        name: "MyNotice",
        component: () => import("@/views/profile/notice/index.vue"),
        meta: { title: "我的通知", icon: "user", hidden: true },
      },
      {
        path: "/detail/:id(\\d+)",
        name: "DemoDetail",
        component: () => import("@/views/demo/detail.vue"),
        meta: { title: "详情页缓存", icon: "user", hidden: true, keepAlive: true },
      },
      {
        path: "product/detail/:id(\\d+)",
        name: "ProductDetail",
        component: () => import("@/views/product/detail.vue"),
        meta: { title: "产品详情", hidden: true },
      },
      {
        path: "product/compare",
        name: "ProductCompare",
        component: () => import("@/views/product/compare.vue"),
        meta: { title: "产品对比", hidden: true },
      },
      // AITC 子页面（动态菜单会自动注册，此处保留作为显式声明）
      {
        path: "aitc/tasks/:taskId(\\d+)",
        name: "TaskDetail",
        component: () => import("@/views/aitc/task/detail.vue"),
        meta: { title: "任务详情", hidden: true },
      },
      {
        path: "aitc/tasks/:taskId(\\d+)/case-review/:itemId(\\d+)",
        name: "AitcCaseReview",
        component: () => import("@/views/aitc/task/case_review/ReviewPage.vue"),
        meta: { title: "用例逐条审核", hidden: true, singleTab: true },
      },
      {
        path: "aitc/tasks/:taskId(\\d+)/case-complete/:itemId(\\d+)",
        name: "AitcCaseComplete",
        component: () => import("@/views/aitc/task/case_complete/ReviewPage.vue"),
        meta: { title: "完善用例", hidden: true, singleTab: true },
      },
      {
        path: "aitc/tasks/:taskId(\\d+)/script-review/:itemId(\\d+)",
        name: "ScriptReview",
        component: () => import("@/views/aitc/task/script_gen/ReviewPage.vue"),
        meta: { title: "脚本审核", hidden: true, singleTab: true },
      },
      {
        path: "aitc/tasks/:taskId(\\d+)/core-review",
        name: "CoreReview",
        component: () => import("@/views/aitc/task/core_select/ReviewPage.vue"),
        meta: { title: "核心挑选审核", hidden: true, singleTab: true },
      },
    ],
  },
];

/**
 * 创建路由
 */
const router = createRouter({
  history: createWebHashHistory(),
  routes: constantRoutes,
  // 刷新时，滚动条位置还原
  scrollBehavior: () => ({ left: 0, top: 0 }),
});

// 全局注册 router
export function setupRouter(app: App<Element>) {
  app.use(router);
}

export default router;
