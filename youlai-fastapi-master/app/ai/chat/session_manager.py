"""会话上下文管理器。

管理会话的页面上下文（project_id、suite_id 等），
以及 Working Context（当前对话中的临时状态）。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionContext:
    """会话上下文 — 存储当前页面信息和对话状态。

    页面上下文（由前端注册）:
        - domain: 当前页面所属域
        - project_id: 当前选中的项目
        - suite_id: 当前选中的套件
        - url: 当前页面路径

    工作上下文（由对话流程产生）:
        - pending_skill: 等待确认的 Skill（ASYNC 模式）
        - selected_cases: 用户当前选中的用例列表
        - last_action: 最近一次操作

    上下文注入状态:
        - last_context_fingerprint: 上次注入时的指纹，用于判断是否需要重新注入
    """

    session_id: int
    domain: str = "case"
    context_json: dict = field(default_factory=dict)
    working: dict = field(default_factory=dict)
    last_context_fingerprint: str = ""

    @property
    def project_id(self) -> int | None:
        return self.context_json.get("project_id")

    @property
    def suite_id(self) -> int | None:
        return self.context_json.get("suite_id")

    @property
    def suite_ids(self) -> list[int] | None:
        """多模块 ID 列表，兼容旧单数 suite_id。"""
        ids = self.context_json.get("suite_ids")
        if ids:
            return [int(i) for i in ids]
        sid = self.context_json.get("suite_id")
        return [int(sid)] if sid else None

    def update_context(self, domain: str | None = None, context_json: dict | None = None):
        """更新页面上下文。"""
        if domain is not None:
            self.domain = domain
        if context_json is not None:
            self.context_json = {**self.context_json, **context_json}

    def set_working(self, key: str, value: Any):
        self.working[key] = value

    def get_working(self, key: str, default: Any = None) -> Any:
        return self.working.get(key, default)

    def clear_working(self):
        self.working.clear()

    @classmethod
    def from_session(cls, session_id: int, domain: str, context_json: dict | None = None):
        return cls(
            session_id=session_id,
            domain=domain,
            context_json=context_json or {},
        )
