"""Skill 基类 + 注册表 + SkillResult。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SkillMode(str, Enum):
    SYNC = "SYNC"    # 对话内同步执行，产出确认卡片
    ASYNC = "ASYNC"  # 批量异步，委托 TaskEngine


@dataclass
class SkillResult:
    """Skill 执行结果。"""
    success: bool = True
    msg_type: str = "text"         # text/action_card/task_card/confirm_card/clarify_card
    content: str = ""               # Markdown 正文
    metadata: dict = field(default_factory=dict)
    error: str | None = None


class BaseSkill(ABC):
    """Skill 基类 — 一个 Skill 对应一种用户意图。

    子类只需实现:
    - 类属性: name, description, domain, mode, keywords
    - parameters_schema() -> dict
    - execute(params, context) -> SkillResult
    """

    name: str = ""
    description: str = ""
    domain: str = ""
    mode: SkillMode = SkillMode.SYNC
    keywords: list[str] = []
    required_page: str = ""  # 该 Skill 只能在指定页面触发（空字符串表示不限制）

    def parameters_schema(self) -> dict:
        """返回 OpenAI function calling 格式的参数定义。
        子类可重写以定义该 Skill 需要的参数。
        """
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def to_openai_tool(self) -> dict:
        """转为 OpenAI tool calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema(),
            },
        }

    @abstractmethod
    async def execute(self, params: dict, context: dict) -> SkillResult:
        """执行技能。

        Args:
            params: 从用户消息中提取的参数
            context: 会话上下文 {session_id, project_id, suite_id, db_session, ...}

        Returns:
            SkillResult 执行结果
        """
        ...


class SkillRegistry:
    """全局 Skill 注册表 — 按域管理。"""

    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}  # name -> skill

    def register(self, skill: BaseSkill):
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' 已注册")
        self._skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill | None:
        return self._skills.get(name)

    def list_by_domain(self, domain: str) -> list[BaseSkill]:
        return [s for s in self._skills.values() if s.domain == domain]

    def list_all(self) -> list[BaseSkill]:
        return list(self._skills.values())

    def get_tools_for_domain(self, domain: str) -> list[dict]:
        """获取某域所有 Skill 的 OpenAI tool 定义。"""
        return [s.to_openai_tool() for s in self.list_by_domain(domain)]


# 全局单例
skill_registry = SkillRegistry()
