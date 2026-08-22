"""TestLink 连接配置。

通过 app.config.settings 读取，配置项可用 .env / 环境变量覆盖：
    TESTLINK_PROVIDER       提供方：mock / xmlrpc / rest
    TESTLINK_BASE_URL       服务地址（mock 服务默认 http://127.0.0.1:8088）
    TESTLINK_API_KEY        API Key（真实系统认证用）
    TESTLINK_PROJECT_ID     TestLink 侧项目 ID（可选，用于默认项目映射）
"""

from app.config import settings


def get_provider() -> str:
    """当前 TestLink 提供方（默认 mock）。"""
    return getattr(settings, "TESTLINK_PROVIDER", "mock") or "mock"


def get_base_url() -> str:
    """TestLink 服务地址。"""
    return getattr(settings, "TESTLINK_BASE_URL", "http://127.0.0.1:8088") or "http://127.0.0.1:8088"


def get_api_key() -> str:
    """API Key（真实系统认证用）。"""
    return getattr(settings, "TESTLINK_API_KEY", "") or ""
