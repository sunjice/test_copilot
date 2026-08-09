"""工具基础设施 — ToolContext + 工具注册表。"""

from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ToolContext:
    """每次请求的工具上下文，注入到所有工具中。

    工具通过此上下文获取 db session、当前页面状态等信息，
    而不是通过全局变量，确保线程/协程安全。
    """

    db: AsyncSession
    session_id: int
    domain: str = "case"
    page_type: str = ""
    context_json: dict[str, Any] = field(default_factory=dict)
    user_id: int = 0  # 操作人 ID，用于审计和权限控制

    # ── 域专属 ID，统一从 context_json 读取（与 SessionContext 模式一致） ──
    @property
    def project_id(self) -> int | None:
        return self.context_json.get("project_id")

    @property
    def suite_id(self) -> int | None:
        return self.context_json.get("suite_id")


# 工具工厂类型
ToolFactory = Callable[["ToolContext"], Any]

# 工具构建器类型
ToolBuilder = Callable[["ToolContext"], list[BaseTool]]


class ToolRegistry:
    """域级工具注册表 — 按 domain 管理工具构建器。"""

    def __init__(self):
        self._builders: dict[str, ToolBuilder] = {}

    def register(self, domain: str, builder: ToolBuilder):
        if domain in self._builders:
            raise ValueError(f"Tool builder for domain '{domain}' 已注册")
        self._builders[domain] = builder

    def get_builder(self, domain: str) -> ToolBuilder | None:
        return self._builders.get(domain)

    def build_tools(self, domain: str, ctx: ToolContext) -> list[BaseTool]:
        builder = self.get_builder(domain)
        if builder is None:
            return []
        return builder(ctx)


# 全局单例
tool_registry = ToolRegistry()
