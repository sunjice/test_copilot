"""canonical 序列化 + SHA256（复用 synced_hash 语义）。

用途：本地用例内容 → 规范化字符串 → SHA256，作为「本地脏检测基准」。
    - 同步时：计算远端内容 hash 写入 synced_hash（作为「与远端一致」的基准）。
    - 本地修改后：重算 hash 与 synced_hash 对比，不一致 → 标记 sync_status=2（待反写）。

canonical 化的核心：字段顺序固定、忽略空值、steps 按 step_no 稳定排序，
确保「语义相同但字段顺序不同」的数据得到同一 hash。
"""

import hashlib
import json
from typing import Any

# 参与脏检测的内容字段（顺序固定，与 field_map 的语义一致）
CANONICAL_FIELDS: tuple[str, ...] = (
    "name",
    "purpose",
    "summary",
    "preconditions",
    "topo",
    "test_data",
    "steps",
)


def _canonical_steps(steps: Any) -> Any:
    """规范化 steps：按 step_no 排序，每个 step 只保留固定键。"""
    if not steps or not isinstance(steps, list):
        return None
    norm: list[dict] = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        norm.append(
            {
                "step_no": s.get("step_no", 0),
                "action": (s.get("action") or "").strip(),
                "expected": (s.get("expected") or "").strip(),
            }
        )
    norm.sort(key=lambda x: (x["step_no"], x["action"], x["expected"]))
    return norm


def canonicalize(fields: dict[str, Any]) -> str:
    """将用例内容字段规范化为一串稳定字符串。

    只取 CANONICAL_FIELDS 中的字段，忽略其它（如 AI 业务字段、同步状态字段），
    空值字段跳过，steps 做稳定排序。
    """
    parts: list[str] = []
    for field in CANONICAL_FIELDS:
        if field not in fields:
            continue
        value = fields[field]
        if field == "steps":
            value = _canonical_steps(value)
        if value in (None, "", [], {}):
            continue
        parts.append(f"{field}={json.dumps(value, ensure_ascii=False, sort_keys=True)}")
    return "\n".join(parts)


def content_hash(fields: dict[str, Any]) -> str:
    """计算用例内容 SHA256（用于 synced_hash 脏检测）。"""
    canon = canonicalize(fields)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def is_dirty(fields: dict[str, Any], synced_hash: str | None) -> bool:
    """判断本地内容相对上次同步是否已变更（脏）。

    Args:
        fields: 当前本地内容字段 dict
        synced_hash: 上次同步时记录的 hash（AiTcCase.synced_hash）

    Returns:
        True 表示本地有未同步的修改
    """
    if not synced_hash:
        # 无基准：有内容即视为脏（新关联但从未同步的用例）
        return bool(canonicalize(fields))
    return content_hash(fields) != synced_hash
