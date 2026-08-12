"""数据清洗工具 — name 预拆词、HTML 去标签、向量文本拼接。"""

import re


def split_name(name: str) -> str:
    """预拆词：去掉 _、驼峰拆分 → 空格分隔。

    Examples:
        "test_login_api"  → "test login api"
        "LoginTest"       → "Login Test"
        "user_name_check" → "user name check"
    """
    if not name:
        return ""

    # 1. 下划线 → 空格
    name = name.replace("_", " ")

    # 2. 驼峰拆分：小写后跟大写 → 中间加空格
    # 如 "LoginTest" → "Login Test", "MyHTTPClient" → "My HTTPClient"
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)

    # 3. 整理多余空格
    name = re.sub(r"\s+", " ", name).strip()

    return name


def strip_html(text: str | None) -> str:
    """去除 HTML 标签，保留纯文本。"""
    if not text:
        return ""
    clean = re.compile(r"<[^>]+>")
    return clean.sub(" ", text).strip()


def steps_to_text(steps: list | None) -> str:
    """将 JSONB 格式的测试步骤转为纯文本。

    Input:  [{"step_no": 1, "action": "打开页面", "expected": "正常显示"}]
    Output: "1. 打开页面 -> 正常显示; 2. ..."
    """
    if not steps or not isinstance(steps, list):
        return ""

    parts: list[str] = []
    for s in steps:
        step_no = s.get("step_no", len(parts) + 1)
        action = strip_html(s.get("action", ""))
        expected = strip_html(s.get("expected", ""))
        if expected:
            parts.append(f"{step_no}. {action} -> {expected}")
        else:
            parts.append(f"{step_no}. {action}")

    return "; ".join(parts)


def build_vector_text(
    name: str,
    purpose: str | None = None,
    summary: str | None = None,
    steps_text: str = "",
    topo: str | None = None,
) -> str:
    """拼接向量化文本（带字段标签 + 换行）。

    字段顺序固定，空字段跳过。
    """
    lines: list[str] = []

    name_clean = split_name(name)
    if name_clean:
        lines.append(f"用例名称: {name_clean}")

    if purpose:
        lines.append(f"测试目的: {purpose}")

    if summary:
        lines.append(f"测试摘要: {summary}")

    if steps_text:
        lines.append(f"测试步骤: {steps_text}")

    if topo:
        lines.append(f"拓扑环境: {topo}")

    return "\n".join(lines)
