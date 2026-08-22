"""TestLink 字段 ↔ 本地 AiTcCase 字段映射。

TestLink 侧字段来自 get_case_detail 返回（见 testlink_api/testlink.txt 示例）：
    item_a           测试项 / 目的
    idea_a           测试思想（描述）
    summary          拓扑标识（如 topo_lan_wan_usb_storage）
    condition_a      前置条件
    steps            HTML 表格（测试步骤 + 预期结果）
    expected_results 预期结果（独立字段，通常为空，预期已并入 steps）
    name             用例名称（如 ftps_login_fali_when_overtime）
    case_id          用例 ID（如 C-2185677）
    version_id       用例版本

本地 AiTcCase 字段：
    purpose          → 测试目的
    summary          → 测试思想
    topo             → 拓扑标识
    preconditions    → 前置条件
    steps            → 测试步骤（JSONB 结构化）
    name             → 用例名称
    external_id      → 外部用例 ID（C-XXXXXXX）

注意：TestLink 的 `summary` 字段语义是「拓扑标识」，与本地 `summary`（测试思想）
语义不同，映射时需特别小心，务必通过本模块常量，勿散落硬编码。
"""

# TestLink → 本地：拉取（pull）时，TestLink 字段到本地 AiTcCase 字段的映射
PULL_FIELD_MAP: dict[str, str] = {
    "item_a": "purpose",
    "idea_a": "summary",
    "summary": "topo",
    "condition_a": "preconditions",
    "name": "name",
    "case_id": "external_id",
}

# 本地 → TestLink：反写（push / update_case）时，本地字段到 TestLink 字段的映射
PUSH_FIELD_MAP: dict[str, str] = {v: k for k, v in PULL_FIELD_MAP.items()}

# steps / expected_results 需特殊解析，不在此映射内（见 parser.py）
STEPS_FIELD = "steps"
EXPECTED_RESULTS_FIELD = "expected_results"


def to_local_field(testlink_field: str) -> str | None:
    """TestLink 字段名 → 本地字段名（未映射返回 None）。"""
    return PULL_FIELD_MAP.get(testlink_field)


def to_testlink_field(local_field: str) -> str | None:
    """本地字段名 → TestLink 字段名（未映射返回 None）。"""
    return PUSH_FIELD_MAP.get(local_field)
