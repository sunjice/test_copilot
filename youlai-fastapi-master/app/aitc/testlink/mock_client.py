"""TestLink Mock 客户端实现。

对接 testlink_api/mock_testlink_server.py 提供的 Mock 服务：
    - get_case_detail  → XML-RPC POST /xmlrpc
    - get_tree_nodes   → GET /get_tree_nodes
    - update_case      → 假设为 XML-RPC（Mock 侧暂未实现，返回 False 并记录日志）

在公司内接入真实 TestLink 后，新增 xmlrpc_client.py / rest_client.py 替换本实现，
本类仅用于本地开发与联调。
"""

import json
import urllib.parse
import urllib.request
from typing import Any

from loguru import logger

from app.aitc.testlink.base import TestCaseDetail, TestLinkClient, TreeNode


class MockTestLinkClient(TestLinkClient):
    """Mock 实现：HTTP + XML-RPC 混合调用本地 Mock 服务。"""

    name = "mock"

    def __init__(self, base_url: str = "http://127.0.0.1:8088") -> None:
        self._base_url = base_url.rstrip("/")

    # ── 基础请求 ──

    def _http_get_json(self, path: str, params: dict | None = None) -> list | dict:
        url = f"{self._base_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _xmlrpc_call(self, method: str, *args) -> Any:
        """调用 Mock 服务的 XML-RPC 端点。

        直接用标准库 xmlrpc.client（Mock 服务实现了 getCaseDetail）。
        """
        import xmlrpc.client

        proxy = xmlrpc.client.ServerProxy(f"{self._base_url}/xmlrpc")
        fn = getattr(proxy, method)
        return fn(*args)

    # ── 接口实现 ──

    async def verify_connection(self) -> bool:
        try:
            self._http_get_json("/health")
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning(f"TestLink mock 连接失败: {e}")
            return False

    async def get_case_detail(self, case_ids: list[str]) -> dict[str, TestCaseDetail]:
        if not case_ids:
            return {}
        raw = self._xmlrpc_call("get_case_detail", case_ids)
        result: dict[str, TestCaseDetail] = {}
        for key, value in (raw or {}).items():
            result[key] = TestCaseDetail(**value)
        return result

    async def get_tree_nodes(
        self,
        node_id: str | None = None,
        tcase_prefix: str | None = None,
        root_node: str | None = None,
    ) -> list[TreeNode]:
        params: dict[str, str] = {}
        if node_id is not None:
            params["node_id"] = node_id
        if tcase_prefix is not None:
            params["tcase_prefix"] = tcase_prefix
        if root_node is not None:
            params["root_node"] = root_node
        raw = self._http_get_json("/get_tree_nodes", params)
        return [TreeNode(**n) for n in (raw or [])]

    async def update_case(self, case_id: str, fields: dict) -> bool:
        # TODO: Mock 服务暂未实现 update_case，待接入真实系统后替换为 XML-RPC/REST 调用
        logger.warning(
            f"[mock] update_case 未实现，case_id={case_id}, fields={fields}"
        )
        return False
