"""TestLink 客户端抽象基类与数据模型。

对外暴露统一接口（仅 3 个）：
    get_case_detail(case_ids) -> dict[str, TestCaseDetail]
    get_tree_nodes(node_id, tcase_prefix, root_node) -> list[TreeNode]
    update_case(case_id, fields) -> bool

通过 provider 注册表切换实现（mock / xmlrpc / rest），
新增实现流程见 __init__.py 顶部注释。
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


# ════════════════════════════════════════════
# 数据模型
# ════════════════════════════════════════════

class TestCaseDetail(BaseModel):
    """get_case_detail 返回的单条用例详情（TestLink 原始字段，共 6 个）。

    注意：真实接口不返回 name / case_id / version_id！
    - name 来自 get_tree_nodes 节点的 name 字段
    - case_id 来自 get_tree_nodes 节点的 case_id 字段
    """

    item_a: str = ""
    idea_a: str = ""
    summary: str = ""          # 注意：TestLink 的 summary 是「拓扑标识」，非测试思想
    condition_a: str = ""
    steps: str = ""            # 带 CSS class/style 的 HTML 表格
    expected_results: str = ""

    class Config:
        extra = "allow"  # 允许额外字段，兼容真实系统返回的其它字段


class TreeNode(BaseModel):
    """get_tree_nodes 返回的树节点。"""

    node_id: str = ""
    type: str = ""             # test_suite / test_case
    name: str = ""
    case_id: str | None = None
    case_count: int | None = None

    class Config:
        extra = "allow"


# ════════════════════════════════════════════
# 抽象基类
# ════════════════════════════════════════════

class TestLinkClient(ABC):
    """TestLink 统一接口。

    实现约定：
    - get_case_detail / get_tree_nodes / update_case 返回统一数据结构
    - 协议差异（XML-RPC / REST / mock）在子类内部消化
    - 不做字段映射（映射在 field_map.py），不写库（持久化在 sync/push service）
    """

    name: str = "base"

    @abstractmethod
    async def verify_connection(self) -> bool:
        """探测连接是否可用。"""
        raise NotImplementedError

    @abstractmethod
    async def get_case_detail(self, case_ids: list[str]) -> dict[str, TestCaseDetail]:
        """按用例 ID 批量取详情。

        Args:
            case_ids: 用例 ID 列表，如 ["C-2185677"]

        Returns:
            {case_id(去横杠): TestCaseDetail}，缺失的 ID 不在返回中
        """
        raise NotImplementedError

    @abstractmethod
    async def get_tree_nodes(
        self,
        node_id: str | None = None,
        tcase_prefix: str | None = None,
        root_node: str | None = None,
    ) -> list[TreeNode]:
        """获取指定节点下一层子节点。

        Args:
            node_id: 节点 ID；为空/根时返回顶层套件列表
            tcase_prefix: 用例前缀（如 "TP-"）
            root_node: 根节点标识（如 "root"）

        Returns:
            节点列表（可能是 test_suite 或 test_case 类型）
        """
        raise NotImplementedError

    @abstractmethod
    async def update_case(self, case_id: str, fields: dict[str, Any]) -> bool:
        """反写用例字段。

        Args:
            case_id: 用例 ID（如 "C-2185677"）
            fields: 要更新的字段（TestLink 字段名 → 值）

        Returns:
            是否更新成功

        TODO: 真实 TestLink 的 update_case 签名需在公司内联调确认，
        这里按常见形态假设（case_id + 字段 dict），字段名沿用 TestLink 原始名。
        """
        raise NotImplementedError
