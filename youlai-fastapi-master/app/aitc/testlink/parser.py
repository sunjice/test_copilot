"""TestLink 数据解析：HTML 清洗、测试步骤结构化解析（核心模块，见方案 §六）。

职责：
    html_to_plain       任意 HTML → 可读纯文本（复用 html_format.html_to_text）
    parse_steps         步骤 HTML → ([{step_no, action, expected}], parse_status)
    parse_case_to_local 用例详情 → 本地字段（原文入 *_raw + 清洗入字段）

步骤解析策略（按优先级尝试，见方案 §6.2）：
    1. <table> 2 列（步骤/预期）或 3 列（序号/步骤/预期）
    2. <ol>/<ul> + <li>（每条一步，内部识别「预期：」分隔）
    3. 连续 <div>/<p> 分段
    4. 纯文本多行（「序号. 操作 -> 预期」模式）
    全部失败 → 降级为纯文本单步，parse_status=2。
"""

import re
from html.parser import HTMLParser

from app.aitc.case.html_format import html_to_text


# ════════════════════════════════════════════
# 通用 HTML 清洗
# ════════════════════════════════════════════

def html_to_plain(html: str) -> str:
    """TestLink 任意 HTML → 可读纯文本（非可逆，用于展示/向量化/AI）。

    复用 html_format.html_to_text 的通用分支（<br>/<p>/<li> → 换行 + 去标签 + 解实体）。
    """
    return html_to_text(html)


# ════════════════════════════════════════════
# 步骤结构化解析
# ════════════════════════════════════════════

_PARSE_OK = 1
_PARSE_DEGRADED = 2
_PARSE_NONE = 0


class _TableParser(HTMLParser):
    """解析 <table> 为行列表，每行是 [cell_text, ...]。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._rows: list[list[str]] = []
        self._in_row = False
        self._in_cell = False
        self._current_row: list[str] = []
        self._current_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "tr":
            self._in_row = True
            self._current_row = []
        elif tag in ("td", "th") and self._in_row:
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._in_cell:
            self._current_row.append("".join(self._current_cell).strip())
            self._in_cell = False
        elif tag == "tr" and self._in_row:
            self._rows.append(self._current_row)
            self._in_row = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)

    @property
    def rows(self) -> list[list[str]]:
        return self._rows


class _ListParser(HTMLParser):
    """解析 <li> 项列表，每项一段文本。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._items: list[str] = []
        self._in_li = False
        self._current: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "li":
            self._in_li = True
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "li" and self._in_li:
            self._items.append("".join(self._current).strip())
            self._in_li = False

    def handle_data(self, data: str) -> None:
        if self._in_li:
            self._current.append(data)

    @property
    def items(self) -> list[str]:
        return self._items


def _split_action_expected(text: str) -> tuple[str, str]:
    """从一段文本里拆分「操作」与「预期」（识别「预期：」/「->」等分隔）。"""
    for sep in ("预期结果", "预期", "期望结果"):
        m = re.search(rf"[:：]?\s*{sep}\s*[:：]\s*", text)
        if m:
            return text[: m.start()].strip(), text[m.end():].strip()
    if "->" in text:
        action, expected = text.split("->", 1)
        return action.strip(), expected.strip()
    return text.strip(), ""


def _parse_table(html: str) -> list[dict] | None:
    parser = _TableParser()
    parser.feed(html)
    rows = parser.rows
    if not rows:
        return None

    steps: list[dict] = []
    header_skipped = False
    for row in rows:
        if not row:
            continue
        # 首行可能是表头（「测试步骤」「预期结果」「序号」等）
        joined = "".join(row)
        if not header_skipped and re.search(r"步骤|预期|序号", joined):
            header_skipped = True
            continue
        header_skipped = True

        # 2 列：步骤/预期；3 列：序号/步骤/预期
        if len(row) >= 3:
            raw_no, action, expected = row[0], row[1], row[2]
        elif len(row) == 2:
            raw_no, action, expected = "", row[0], row[1]
        else:
            action, expected = _split_action_expected(row[0])
            raw_no = ""

        action, expected = html_to_plain(action), html_to_plain(expected)
        step_no = len(steps) + 1
        m = re.match(r"^\s*(\d+)[.、)\s]*", raw_no or action)
        if m:
            step_no = int(m.group(1))
            if raw_no == "":
                action = action[m.end():].strip()

        if not action and not expected:
            continue
        steps.append({"step_no": step_no, "action": action, "expected": expected})

    return steps or None


def _parse_list(html: str) -> list[dict] | None:
    parser = _ListParser()
    parser.feed(html)
    items = parser.items
    if not items:
        return None
    steps: list[dict] = []
    for i, item in enumerate(items, start=1):
        text = html_to_plain(item)
        action, expected = _split_action_expected(text)
        if not action and not expected:
            continue
        steps.append({"step_no": i, "action": action, "expected": expected})
    return steps or None


def _parse_blocks(html: str) -> list[dict] | None:
    """连续 <div>/<p> 分段，每段一步。"""
    plain = html_to_plain(html)
    blocks = [b.strip() for b in re.split(r"\n{2,}", plain) if b.strip()]
    if len(blocks) < 2:
        return None
    steps: list[dict] = []
    for i, block in enumerate(blocks, start=1):
        action, expected = _split_action_expected(block)
        steps.append({"step_no": i, "action": action, "expected": expected})
    return steps


def _parse_plain_lines(text: str) -> list[dict] | None:
    """纯文本多行：识别「序号. 操作 -> 预期」模式。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    steps: list[dict] = []
    for ln in lines:
        m = re.match(r"^\s*(\d+)[.、)]\s*(.*)$", ln)
        if m:
            step_no = int(m.group(1))
            rest = m.group(2)
        else:
            step_no = len(steps) + 1
            rest = ln
        action, expected = _split_action_expected(rest)
        steps.append({"step_no": step_no, "action": action, "expected": expected})

    # 若一行都没识别出「序号」，视为无法可靠结构化
    if not any(re.match(r"^\s*\d+[.、)]", ln) for ln in lines):
        return None
    return steps


def parse_steps(html: str) -> tuple[list[dict], int]:
    """解析步骤 HTML → ([{step_no, action, expected}], parse_status)。

    parse_status: 1-解析成功 2-降级为纯文本 0-无步骤
    """
    if not html or not html.strip():
        return [], _PARSE_NONE

    for fn in (_parse_table, _parse_list, _parse_blocks):
        steps = fn(html)
        if steps:
            return steps, _PARSE_OK

    # 纯文本多行兜底
    plain = html_to_plain(html)
    steps = _parse_plain_lines(plain)
    if steps:
        return steps, _PARSE_OK

    # 降级：整个 HTML 转纯文本，作为单步
    text = plain.strip()
    if text:
        return [{"step_no": 1, "action": text, "expected": ""}], _PARSE_DEGRADED
    return [], _PARSE_NONE


# ════════════════════════════════════════════
# 用例详情 → 本地字段（双轨）
# ════════════════════════════════════════════

def parse_case_to_local(case_id: str, detail: dict) -> dict:
    """将 TestLink 用例详情转为本地 AiTcCase 字段字典（双轨）。

    - 原文 HTML → *_raw 字段（summary_raw/preconditions_raw/steps_raw/test_data_raw）
    - 清洗 → summary/preconditions/steps 等结构化字段
    - steps 解析状态 → steps_parse_status

    Args:
        case_id: 用例 ID（去横杠形式，如 C2185677）
        detail: TestCaseDetail 的 dict 形式

    Returns:
        本地字段 dict
    """
    from app.aitc.testlink.field_map import PULL_FIELD_MAP

    local: dict = {"external_id": case_id}

    # 1. 原文 HTML 入 *_raw
    local["summary_raw"] = detail.get("idea_a") or ""
    local["preconditions_raw"] = detail.get("condition_a") or ""
    local["steps_raw"] = detail.get("steps") or ""
    local["test_data_raw"] = detail.get("test_data") or ""

    # 2. 清洗入结构化字段（name / case_id 不在此接口，由 get_tree_nodes 节点提供）
    for tl_field, local_field in PULL_FIELD_MAP.items():
        if tl_field in ("name", "case_id"):
            continue
        local[local_field] = html_to_plain(detail.get(tl_field) or "")

    # 3. steps 结构化解析 + 状态
    steps, parse_status = parse_steps(detail.get("steps") or "")
    local["steps"] = steps
    local["steps_parse_status"] = parse_status

    return local
