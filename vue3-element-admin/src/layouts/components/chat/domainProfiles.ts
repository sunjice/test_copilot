/** AI 对话 — 域 Profile 配置（按域驱动 UI）。
 *
 * 每个 domain 定义自己的欢迎语、快捷卡片、技能标签映射、以及 UI 开关。
 * 切域时 useChatPanel 从本表读取对应 profile，动态切换整套 UI。
 *
 * 扩展新域：在此处新增一项 profile 即可（后端零改动，仅前端留扩展点）。
 */

import {
  Search, View, EditPen,
} from "@element-plus/icons-vue"
import { TASK_TYPE_MAP } from "@/views/aitc/constants"

/** 快捷提问卡片 */
export interface QuickAction {
  title: string
  desc: string
  prompt: string
  skill: string
  icon: any
  bg: string
}

/** 域 Profile */
export interface DomainProfile {
  /** 欢迎页主标题 */
  welcomeTitle: string
  /** 欢迎页副标题 */
  welcomeSubtitle: string
  /** 快捷提问卡片（空数组则不显示） */
  quickActions: QuickAction[]
  /** 技能名 → 中文标签（"/" 命令补全展示用） */
  skillLabels: Record<string, string>
  /** 是否展示 "/" 命令补全（kb 域无 skill，恒 false） */
  showSlash: boolean
  /** 是否展示上下文栏（kb 域无业务上下文，恒 false） */
  showContextBar: boolean
  /** 输入框占位符 */
  inputPlaceholder: string
}

/** case 域 — 测试用例专业对话 */
const caseProfile: DomainProfile = {
  welcomeTitle: "有什么我能帮你的吗？",
  welcomeSubtitle: "我可以帮你挑选核心用例、审核用例质量、完善用例步骤、生成测试脚本等",
  quickActions: [
    {
      title: "挑选核心用例",
      desc: "从当前模块智能挑选最重要的用例",
      prompt: "/core_select 帮我挑选核心用例",
      skill: "core_select",
      icon: Search,
      bg: "linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%)",
    },
    {
      title: "审核用例质量",
      desc: "检查字段完整性和步骤规范性",
      prompt: "/case_review 审核用例质量",
      skill: "case_review",
      icon: View,
      bg: "linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%)",
    },
    {
      title: "完善测试用例",
      desc: "自动补全用例的缺失字段和测试步骤",
      prompt: "/case_complete 完善测试用例",
      skill: "case_complete",
      icon: EditPen,
      bg: "linear-gradient(135deg, #ffedd5 0%, #fed7aa 100%)",
    },
  ],
  skillLabels: {
    core_select: "挑选核心用例",
    case_review: "审核用例质量",
    script_gen: "生成测试脚本",
    case_complete: "完善测试用例",
    case_design: "设计测试用例",
  },
  showSlash: true,
  showContextBar: true,
  inputPlaceholder: `提问，或输入 "/" 触发任务命令`,
}

/** kb 域 — 普通知识库问答（独立页，无卡片/命令/上下文） */
const kbProfile: DomainProfile = {
  welcomeTitle: "有什么我能帮你的吗？",
  welcomeSubtitle: "Todo: 我可以帮你解答测试设计、问题定位、测试分析等知识库问答",
  quickActions: [],
  skillLabels: {},
  showSlash: false,
  showContextBar: false,
  inputPlaceholder: "输入你的问题…",
}

/** bug 域 — 预留扩展点（本期不落地业务） */
const bugProfile: DomainProfile = {
  welcomeTitle: "有什么我能帮你的吗？",
  welcomeSubtitle: "我可以帮你处理 Bug 相关事务",
  quickActions: [],
  skillLabels: {},
  showSlash: false,
  showContextBar: false,
  inputPlaceholder: "输入你的问题…",
}

/** exec 域 — 预留扩展点（本期不落地业务） */
const execProfile: DomainProfile = {
  welcomeTitle: "有什么我能帮你的吗？",
  welcomeSubtitle: "",
  quickActions: [],
  skillLabels: {},
  showSlash: false,
  showContextBar: false,
  inputPlaceholder: "输入你的问题…",
}

/** 全量域 Profile 表 */
export const domainProfiles: Record<string, DomainProfile> = {
  case: caseProfile,
  kb: kbProfile,
  bug: bugProfile,
  exec: execProfile,
}

/** 取指定域 profile（未配置时回退 case） */
export function getDomainProfile(domain: string): DomainProfile {
  return domainProfiles[domain] ?? caseProfile
}

/** 技能名 → 中文标签（profile 优先，回退 TASK_TYPE_MAP，再回退原始名） */
export function resolveSkillLabel(domain: string, name: string): string {
  const profile = getDomainProfile(domain)
  return profile.skillLabels[name] || TASK_TYPE_MAP[name]?.label || name
}
