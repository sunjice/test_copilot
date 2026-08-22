"""可逆 text↔HTML 固定格式规范。

背景
----
AI 审核/补全产生纯文本，反写 TestLink 时需转 HTML；TestLink 回传又是 HTML。
为保证「AI 反写后的字段能被无损解回纯文本供 AI 再次消费」，提供成对、可逆的转换：

    text_to_html(text)  → 固定格式 HTML（带 <div class="tc-plain"> 标记）
    html_to_text(html)  → 纯文本（优先识别本系统标记；对任意 HTML 退化为通用清洗）

与 cleaner.py::strip_html 的关系：
    strip_html     只去标签（不还原换行），用于向量化/ES 等精简场景；
    html_to_text   还原换行（<br>/<p>/<li> → \\n），用于 AI 消费与可读展示。
"""

import html as _html
import re

# 本系统生成的固定格式标记，用于反写后回拉时精准识别并无损还原
PLAIN_MARKER = "tc-plain"


def text_to_html(text: str) -> str:
    """纯文本 → 固定格式 HTML（可逆）。

    规则：
        1. 转义 & < > "（防注入/破坏结构）
        2. 空行 → 段落分隔 <p>；单换行 → <br>
        3. 统一包在 <div class="tc-plain"> 内，便于识别本系统生成内容
    """
    if text is None:
        text = ""
    # 1. 转义（& 必须先转，避免二次转义）
    text = _html.escape(text, quote=True)

    # 2. 换行还原：先按空行分段，再处理单换行
    paragraphs = text.split("\n\n")
    parts: list[str] = []
    for para in paragraphs:
        if para == "":
            continue
        # 段内单换行 → <br>
        para_html = para.replace("\n", "<br>")
        parts.append(f"<p>{para_html}</p>")

    body = "".join(parts)
    return f'<div class="{PLAIN_MARKER}">{body}</div>'


def html_to_text(html: str) -> str:
    """HTML → 纯文本（text_to_html 的逆）。

    优先识别本系统生成的固定格式（class="tc-plain"）；否则退化为通用清洗：
    <br>/<p>/<li> → 换行，去剩余标签，解实体，压缩多余空行。
    """
    if not html:
        return ""

    # 识别本系统标记，抽取标记内部内容
    marker_re = re.compile(
        rf'<div[^>]*class=["\'][^"\']*{PLAIN_MARKER}[^"\']*["\'][^>]*>(.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    )
    m = marker_re.search(html)
    inner = m.group(1) if m else html

    # 还原换行（仅针对块级标签）
    inner = re.sub(r"<br\s*/?>", "\n", inner, flags=re.IGNORECASE)
    inner = re.sub(r"</p\s*>", "\n", inner, flags=re.IGNORECASE)
    inner = re.sub(r"<p[^>]*>", "", inner, flags=re.IGNORECASE)
    inner = re.sub(r"</li\s*>", "\n", inner, flags=re.IGNORECASE)
    inner = re.sub(r"<li[^>]*>", "", inner, flags=re.IGNORECASE)

    # 去剩余标签
    inner = re.sub(r"<[^>]+>", "", inner)

    # 解实体
    inner = _html.unescape(inner)

    # 压缩多余空行（>2 连续换行 → 2），并去除首尾空行
    inner = re.sub(r"\n{3,}", "\n\n", inner)
    return inner.strip()


def html_to_plain(html: str) -> str:
    """TestLink 任意 HTML → 可读纯文本（非可逆，用于展示/向量化/AI）。

    等价于 html_to_text 的通用分支，语义更明确，供 parser.py 复用。
    """
    return html_to_text(html)


def steps_to_html(steps: list | None) -> str:
    """结构化步骤 [{step_no, action, expected}] → HTML 表格（反写 TestLink 用）。

    输出 3 列格式：
        <table><tbody>
          <tr><th>步骤</th><th>操作</th><th>预期结果</th></tr>
          <tr><td>1</td><td>xxx</td><td>yyy</td></tr>
        </tbody></table>
    """
    if not steps or not isinstance(steps, list):
        return ""

    rows = ["<table><tbody>", "<tr><th>步骤</th><th>操作</th><th>预期结果</th></tr>"]
    for i, s in enumerate(steps, start=1):
        if not isinstance(s, dict):
            continue
        step_no = s.get("step_no", i)
        action = _html.escape(str(s.get("action") or ""), quote=True)
        expected = _html.escape(str(s.get("expected") or ""), quote=True)
        rows.append(f"<tr><td>{step_no}</td><td>{action}</td><td>{expected}</td></tr>")
    rows.append("</tbody></table>")
    return "".join(rows)
