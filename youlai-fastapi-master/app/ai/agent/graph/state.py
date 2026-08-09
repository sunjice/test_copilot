"""Agent 状态定义 — 扩展 LangGraph MessagesState，携带会话上下文。

P1+ 接入 Postgres Checkpointer 后，thread_id = session_id 即可实现跨请求断点续跑。
"""

from typing import Any

from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Agent 图状态。

    messages 字段继承自 MessagesState（list[BaseMessage]），
    图循环中 agent_node 和 tool_node 自动读写此字段。
    """

    # ── 会话上下文（由外部注入，图只读） ──
    session_id: int = 0
    domain: str = "case"
    user_id: int = 0

    # ── system_prompt — 每请求动态注入，agent_node 从 state 读取（不再走闭包） ──
    system_prompt: str = ""

    # ── 页面上下文（来自前端 aiContext 注册） ──
    page_type: str = ""
    context_json: dict[str, Any] = {}

    # ── 产出物（工具执行后收集，runner 用于 SSE 卡片推送） ──
    collected_card: dict[str, Any] | None = None

    # ── create_react_agent 内部控制字段 ──
    remaining_steps: int = 25
