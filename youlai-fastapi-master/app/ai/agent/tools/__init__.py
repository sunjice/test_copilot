"""Agent Tools — LLM 可自主调用的工具集合。

与 Skill 不同：工具是纯函数，模型自主决定何时调用、传什么参数。
工具仅做薄封装，业务逻辑仍走 aitc/*/service.py。
"""

from app.ai.agent.tools import case  # noqa: F401
