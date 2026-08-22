/**
 * HTML 安全清洗工具（XSS 防护）
 *
 * 用于渲染 TestLink 等外部来源的富文本（*_raw 字段）。
 * 通过 DOMPurify 白名单过滤，清除 script / 事件属性等危险内容。
 */

import DOMPurify from "dompurify";

/** 允许的标签白名单（正文富文本，保守起见只保留基础排版标签） */
const ALLOWED_TAGS = [
  "p",
  "br",
  "div",
  "span",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
  "ul",
  "ol",
  "li",
  "b",
  "strong",
  "i",
  "em",
  "u",
  "s",
  "h1",
  "h2",
  "h3",
  "h4",
  "blockquote",
  "pre",
  "code",
];

/** 允许的属性（仅保留 href 等安全属性，禁用所有事件属性） */
const ALLOWED_ATTR = ["href", "title", "class", "style"];

export function sanitizeHtml(html: string | null | undefined): string {
  if (!html) return "";
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
  });
}

/**
 * 富文本渲染取值：优先 *_raw 原文（清洗后），回退清洗字段纯文本。
 * 清洗字段（如 summary）是纯文本，直接返回即可（无需清洗）。
 */
export function renderHtml(raw: string | null | undefined, fallback: string | null | undefined): string {
  if (raw) {
    return sanitizeHtml(raw);
  }
  // 纯文本回退：转义为安全 HTML（避免纯文本里的 < > 被当作标签）
  return sanitizeHtml(fallback || "");
}
