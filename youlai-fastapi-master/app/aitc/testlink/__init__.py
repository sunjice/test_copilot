"""TestLink 集成包。

Provider 注册表模式（与 retrieval/common/embedding 一致）：
    mock   本地 Mock 服务（开发联调用，对接 testlink_api/mock_testlink_server.py）
    xmlrpc 真实 TestLink XML-RPC（公司内实现，TODO）
    rest   真实 TestLink REST（公司内实现，TODO）

扩展新 provider 流程：
    1. 新增类，继承 app.aitc.testlink.base.TestLinkClient
    2. 调用 register_provider("名称", 类) 注册
    3. 配置 TESTLINK_PROVIDER=名称 切换

当前仅 mock 可用，公司内需实现 xmlrpc / rest 后注册。
"""

from app.aitc.testlink.base import TestCaseDetail, TestLinkClient, TreeNode
from app.aitc.testlink.config import get_provider as _get_provider_name
from app.aitc.testlink.mock_client import MockTestLinkClient

_REGISTRY: dict[str, type[TestLinkClient]] = {
    "mock": MockTestLinkClient,
    # "xmlrpc": XmlRpcTestLinkClient,   # TODO: 公司内实现
    # "rest": RestTestLinkClient,        # TODO: 公司内实现
}


def register_provider(name: str, cls: type[TestLinkClient]) -> None:
    """注册自定义 provider（名称小写存储）。"""
    _REGISTRY[name.strip().lower()] = cls


def get_client(name: str | None = None) -> TestLinkClient:
    """获取 TestLink 客户端实例（默认取配置 TESTLINK_PROVIDER）。

    Args:
        name: provider 名称（mock / xmlrpc / rest），缺省用配置

    Returns:
        TestLinkClient 实例

    Raises:
        ValueError: 未知 provider
    """
    from app.aitc.testlink.config import get_base_url

    key = (name or _get_provider_name() or "mock").strip().lower()
    cls = _REGISTRY.get(key)
    if cls is None:
        raise ValueError(
            f"未知 TESTLINK_PROVIDER: {key!r}，可选: {', '.join(sorted(_REGISTRY))}"
        )
    # mock 客户端需要 base_url；其余 provider 构造签名可能不同，统一用工厂参数兜底
    if key == "mock":
        return cls(base_url=get_base_url())
    return cls()


__all__ = [
    "TestCaseDetail",
    "TestLinkClient",
    "TreeNode",
    "register_provider",
    "get_client",
]
