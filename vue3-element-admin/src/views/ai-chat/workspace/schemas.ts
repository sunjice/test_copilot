/**
 * 工作区（上下文选择器）— 领域配置
 *
 * 左侧工作区根据当前领域类型（用例 / Bug / 测试项目）切换成不同的层级树。
 *
 * 本期只实现 case 域（复用 ProjectAPI / SuiteAPI：项目 → 模块 → 用例）。
 * bug / exec 域占位，待后端建数据源后接入（disabled = true）。
 */

export interface DomainSchema {
  /** 领域标识，与后端 domain 对齐 */
  domain: string
  /** 领域显示名 */
  label: string
  /** 占位领域（数据源未建，Tab 禁用） */
  disabled?: boolean
}

export const SCHEMAS: Record<string, DomainSchema> = {
  case: {
    domain: "case",
    label: "用例",
  },
  bug: {
    domain: "bug",
    label: "Bug",
    disabled: true,
  },
  exec: {
    domain: "exec",
    label: "测试项目",
    disabled: true,
  },
}

/** 领域 Tab 顺序 */
export const DOMAIN_ORDER = ["case", "bug", "exec"]
