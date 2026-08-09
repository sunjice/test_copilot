"""LangGraph 图构建 — 使用 langgraph.prebuilt.create_react_agent。

架构要点（修复 P0 闭包 bug）：
- LLM 实例按 (model, api_base) 指纹缓存，避免每请求重建 httpx client
- 图每次请求重建（工具携带请求级 db session），编译开销 <100ms，可忽略
- system_prompt 通过 AgentState.system_prompt 字段注入，agent_node 动态读取，不走闭包
- 使用 prebuilt 的 ToolNode（自带并行 tool_calls、错误处理）
"""

import time

from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.ai.agent.graph.state import AgentState
from app.ai.config import AiConfigSnapshot

# ═══════════════ LLM 实例缓存 ═══════════════
# key = (model, api_base, temperature, max_tokens)，api_key 不参与缓存
# （不同请求可能用不同 key，但同一部署 key 不同模型相同 → 共用连接池）
_llm_cache: dict[str, ChatOpenAI] = {}


def _llm_fingerprint(cfg: AiConfigSnapshot) -> str:
    # 注意：api_key 不参与缓存指纹，因为不同请求可能用不同 key，
    # 但同部署的模型/温度/token数相同 → 可以安全复用连接池
    return f"{cfg.model}|{cfg.api_base}|{cfg.temperature or 0.3}|{cfg.max_tokens or 4096}"


def _get_or_create_llm(cfg: AiConfigSnapshot) -> ChatOpenAI:
    fp = _llm_fingerprint(cfg)
    if fp not in _llm_cache:
        _llm_cache[fp] = ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base,
            temperature=cfg.temperature or 0.3,
            max_tokens=cfg.max_tokens or 4096,
            timeout=60.0,            # LLM 调用超时（降到 60s，更快失败）
            max_retries=2,           # 网络波动自动重试
            streaming=True,          # 必须开启，否则 astream_events 收不到 on_chat_model_stream
        )
    return _llm_cache[fp]


async def prewarm_llm() -> None:
    """应用启动时预热 LLM 客户端，避免首请求卡 2 秒等待 httpx 连接。"""
    from app.ai.config import resolve_ai_config
    from loguru import logger
    t0 = time.time()
    try:
        cfg = resolve_ai_config("chat")
        _get_or_create_llm(cfg)
        dt = int((time.time() - t0) * 1000)
        logger.info(f"LLM 预热完成 model={cfg.model} base_url={cfg.api_base} 耗时={dt}ms")
    except Exception as e:
        dt = int((time.time() - t0) * 1000)
        logger.warning(f"LLM 预热失败（不影响正常使用）耗时={dt}ms error={e}")


# ═══════════════ 图构建 ═══════════════


def build_agent_graph(
    tools: list[BaseTool],
    ai_config: AiConfigSnapshot,
) -> CompiledStateGraph:
    """构建 agent 图（每次请求调用，携带请求级 tools / db session）。

    使用 langgraph.prebuilt.create_react_agent，自动处理：
    - ToolNode（错误处理、并行 tool_calls）
    - ReAct 循环路由
    - 中断 / 恢复（配合 Checkpointer）

    system_prompt 从 AgentState.system_prompt 动态读取，每请求注入。
    """
    llm = _get_or_create_llm(ai_config)

    # prompt 函数：每次 agent_node 执行时从 state 读取最新 system_prompt
    # 这是修复闭包 bug 的关键 —— prompt 不走闭包，走 state
    # 注意：create_react_agent 对 callable prompt 不会自动追加 state["messages"]，
    #       必须手动把对话历史拼到 SystemMessage 后面。
    def _prompt_fn(state: AgentState) -> list[SystemMessage]:
        content = state.get("system_prompt", "")
        if not content:
            content = "你是测试部的 AI 助手，帮助测试工程师管理测试用例。"
        return [SystemMessage(content=content)] + state.get("messages", [])

    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=_prompt_fn,
        state_schema=AgentState,
    )
