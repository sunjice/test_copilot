"""AgentRunner — LangGraph create_react_agent + astream_events → SSE 协议映射。

协议映射:
  on_chat_model_stream → chunk 事件（流式文本 + 收集 token usage）
  on_tool_start        → tool_start 事件
  on_tool_end          → tool_end 事件（卡片通过 ToolMessage.artifact 收集）
  最终                  → message + done 事件

架构要点:
- 图每次请求重建（携带请求级 db session 的 tools），避免闭包 bug
- 卡片数据优先从 ToolMessage.artifact 读取（content_and_artifact 模式）
- 历史消息按 token 数截断（trim_messages），保留 tool_calls 配对
- Token 计量通过 LangChainTokenCallback 自动拦截
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator

import tiktoken
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage, trim_messages
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from app.ai.agent.graph.builder import build_agent_graph
from app.ai.agent.graph.state import AgentState
from app.ai.chat.session_manager import SessionContext
from app.ai.chat.usage_logger import LangChainTokenCallback, TokenMeter
from app.ai.config import AiConfigSnapshot
from app.ai.llm_log.writer import LlmLogWriter, make_trace_id

# ── 生产韧性配置 ──
RECURSION_LIMIT = 25          # 图级递归限制（替代 runner 内手动计数）
MAX_HISTORY_TOKENS = 8000     # 历史消息最大 token 数
MAX_HISTORY_MESSAGES = 40     # 历史消息条数上限（兜底）
AGENT_TIMEOUT = 150.0         # agent 整体执行超时（秒），超时后返回错误事件
# 卡片 msg_type 集合
CARD_MSG_TYPES = {"confirm_card", "clarify_card"}


class AgentRunner:
    """Agent 运行器 — 封装 LangGraph 图执行和 SSE 事件流。"""

    # ═══════════════ 公共接口 ═══════════════

    async def run(
        self,
        message: str,
        context: SessionContext,
        history: list[dict] | None,
        tools: list[BaseTool],
        system_prompt: str,
        ai_config: AiConfigSnapshot,
    ) -> AsyncGenerator[str, None]:
        """执行 agent 图，流式返回 SSE 事件字符串。

        与 ChatOrchestrator.process_message() 接口兼容，
        外部调用方不需要改动。
        """
        # ── 构建图（每请求重建，携带请求级 tools/db session） ──
        graph: CompiledStateGraph = build_agent_graph(tools, ai_config)

        # ── 组装初始消息（token-aware 截断，保留 tool_calls 配对） ──
        init_messages = self._build_history(history, message)

        # ── 初始状态（system_prompt 注入到 state，agent_node 动态读取） ──
        user_id = context.context_json.get("user_id") or 0
        state = AgentState(
            messages=init_messages,
            session_id=context.session_id,
            domain=context.domain,
            user_id=user_id,
            project_id=context.project_id,
            suite_id=context.suite_id,
            page_type=context.context_json.get("current_page", ""),
            context_json=context.context_json,
            system_prompt=system_prompt,
        )

        # ── 图配置（thread_id 为 Checkpointer 预留） ──
        graph_config: dict[str, Any] = {
            "configurable": {"thread_id": str(context.session_id)},
            "recursion_limit": RECURSION_LIMIT,
        }

        # ── Token 计量 ──
        meter = TokenMeter(model=ai_config.model or "unknown")
        token_callback = LangChainTokenCallback(meter)
        graph_config["callbacks"] = [token_callback]

        # ── LLM 日志 ──
        trace_id = context.get_working("trace_id") or make_trace_id("agent", context.session_id)
        t_start = time.time()

        # ── 立即发送 thinking 事件，让前端知道 agent 已开始工作 ──
        yield self._sse("thinking", {"message": "AI 正在思考..."})

        collected_content = ""
        collected_card: dict | None = None
        tool_call_count = 0
        tool_names: list[str] = []  # 收集已调用的工具名称（按调用顺序）

        try:
            # 用 asyncio.wait_for 包裹，防止无限挂起
            async for event in _astream_with_timeout(graph, state, graph_config, AGENT_TIMEOUT):
                kind = event.get("event", "")

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and chunk.content:
                        collected_content += chunk.content
                        yield self._sse("chunk", {"content": chunk.content})

                elif kind == "on_tool_start":
                    tool_call_count += 1
                    data = event.get("data", {}) or {}
                    # astream_events v2 工具名在 event["name"]；v1 可能在 data["name"]
                    name = data.get("name") or event.get("name") or ""
                    tool_input = data.get("input", {})
                    if name:
                        tool_names.append(name)
                    yield self._sse("tool_start", {"name": name, "args": tool_input})

                elif kind == "on_tool_end":
                    data = event.get("data", {}) or {}
                    output = data.get("output", "")
                    name = data.get("name") or event.get("name") or ""

                    # 卡片数据：优先从 ToolMessage.artifact 读取
                    card = self._extract_card(output)
                    if card:
                        collected_card = card

                    yield self._sse("tool_end", {"name": name, "summary": self._summarize(output)})

                elif kind == "on_timeout":
                    duration_ms = int((time.time() - t_start) * 1000)
                    msg = event.get("data", {}).get("message", "Agent 执行超时")
                    await self._write_log(
                        trace_id, context.session_id, ai_config, "timeout", msg, None,
                        duration_ms, meter.prompt_tokens, meter.completion_tokens,
                    )
                    yield self._sse("error", {"message": msg})
                    yield self._sse("done", {})
                    return

        except Exception as e:
            duration_ms = int((time.time() - t_start) * 1000)
            await self._write_log(
                trace_id, context.session_id, ai_config, "error", str(e), None,
                duration_ms, meter.prompt_tokens, meter.completion_tokens,
            )
            yield self._sse("error", {"message": str(e)})
            yield self._sse("done", {})
            return

        # ── 最终回复（合并卡片数据） ──
        duration_ms = int((time.time() - t_start) * 1000)

        if collected_content or collected_card:
            if collected_card:
                final_msg_type = collected_card.get("msg_type", "text")
                final_metadata = collected_card.get("metadata") or {}
                # 卡片类消息优先用 artifact.content 作为主内容（如 clarify_card 的 title），
                # agent 文本兜底。确保前端渲染的标题不会丢失。
                final_content = collected_card.get("content") or collected_content or ""
            else:
                final_msg_type = "text"
                final_metadata = {}
                final_content = collected_content or ""

            final_metadata.update({
                "tool_names": tool_names,
                "tool_calls": tool_call_count,
                "duration_ms": duration_ms,
                "tokens": {
                    "prompt": meter.prompt_tokens,
                    "completion": meter.completion_tokens,
                    "total": meter.total_tokens,
                },
            })

            yield self._sse("message", {
                "role": "assistant",
                "msg_type": final_msg_type,
                "content": final_content,
                "metadata": final_metadata,
            })

        yield self._sse("done", {})

        # ── 异步写日志（不阻塞 SSE 流） ──
        await self._write_log(
            trace_id, context.session_id, ai_config, "success", None, collected_content,
            duration_ms, meter.prompt_tokens, meter.completion_tokens,
        )

    # ═══════════════ 内部方法 ═══════════════

    @staticmethod
    def _build_history(
        history: list[dict] | None,
        current_message: str,
    ) -> list[BaseMessage]:
        """构建初始消息列表。

        - 保留 tool_calls / ToolMessage 配对，让模型理解之前的工具调用上下文
        - token-aware 截断：优先按 token 数截断，兜底按条数
        """
        messages: list[BaseMessage] = []

        if history:
            # 先构建完整的消息列表（保留 tool 消息）
            for h in history[-MAX_HISTORY_MESSAGES:]:
                role = h.get("role", "")
                content = h.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    tool_calls_data = h.get("tool_calls")
                    if tool_calls_data:
                        messages.append(AIMessage(
                            content=content or "",
                            tool_calls=_normalize_tool_calls(tool_calls_data),
                        ))
                    else:
                        # 空 content 的 AIMessage 可能导致 API 报错，给占位文本
                        messages.append(AIMessage(content=content or " "))
                elif role == "tool":
                    messages.append(ToolMessage(
                        content=content or "",
                        tool_call_id=h.get("tool_call_id", ""),
                        name=h.get("name", ""),
                    ))

        messages.append(HumanMessage(content=current_message))

        # Token 截断（保留最近的消息，从 HumanMessage 开始）
        if len(messages) > 1:
            try:
                trimmed = trim_messages(
                    messages,
                    max_tokens=MAX_HISTORY_TOKENS,
                    strategy="last",
                    token_counter=_token_counter,
                    include_system=False,
                    allow_partial=False,
                    start_on="human",
                )
                messages = list(trimmed)
            except Exception:
                pass  # trim 失败不影响主流程

        return messages

    @staticmethod
    def _extract_card(output: Any) -> dict | None:
        """从工具输出中提取卡片数据。

        优先级:
        1. ToolMessage.artifact（content_and_artifact 模式）
        2. ToolMessage.content → JSON 解析（回退兼容）
        3. 直接 JSON 字符串解析（旧工具兼容）
        """
        # 1. artifact 属性（content_and_artifact 模式）
        if hasattr(output, "artifact") and output.artifact:
            data = output.artifact
            if isinstance(data, dict) and data.get("msg_type") in CARD_MSG_TYPES:
                return data

        # 2. ToolMessage content → JSON 解析
        content = None
        if hasattr(output, "content"):
            content = output.content
        elif isinstance(output, str):
            content = output

        if content and isinstance(content, str):
            try:
                data = json.loads(content)
                if isinstance(data, dict) and data.get("msg_type") in CARD_MSG_TYPES:
                    return data
            except (json.JSONDecodeError, TypeError):
                pass

        return None

    @staticmethod
    def _summarize(output: Any) -> str:
        """生成工具输出的简短摘要（用于 tool_end 事件）。"""
        if not output:
            return "（无输出）"

        content = output
        if hasattr(output, "content"):
            content = output.content

        if isinstance(content, str) and content:
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    text = data.get("content", "")
                    if text:
                        return text[:120] + ("..." if len(text) > 120 else "")
                    return "成功" if data.get("success", True) else "失败"
            except (json.JSONDecodeError, TypeError):
                pass

        text = str(content)[:120] if content else "（无输出）"
        return text + ("..." if len(str(content)) > 120 else "")

    @staticmethod
    async def _write_log(
        trace_id: str,
        session_id: int,
        ai_config: AiConfigSnapshot,
        status: str,
        error_msg: str | None,
        response_text: str | None,
        duration_ms: int,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """写入 LLM 调用日志（agent 模式含 token 统计）。"""
        try:
            await LlmLogWriter.write(
                trace_id=trace_id,
                span_seq=0,
                attempt=0,
                module="agent",
                action="agent_run",
                session_id=session_id,
                model=ai_config.model or "unknown",
                status=status,
                error_msg=error_msg,
                messages=[],
                response_raw=response_text or "",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=duration_ms,
            )
        except Exception:
            pass  # 日志写入失败不影响主流程

    @staticmethod
    def _sse(event: str, data: dict) -> str:
        """构造 SSE 事件字符串。"""
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ═══════════════ 模块级工具函数 ═══════════════


def _token_counter(messages: list[BaseMessage]) -> int:
    """基于 tiktoken cl100k_base 的本地 token 计数（不联网、不初始化 LLM）。"""
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        total = 0
        for m in messages:
            content = m.content
            if isinstance(content, str):
                total += len(enc.encode(content))
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        text = part.get("text") or ""
                        if text:
                            total += len(enc.encode(text))
        return total
    except Exception:
        # 兜底：按字符数估算，确保 trim 不阻塞主流程
        return sum(len(str(m.content)) for m in messages)


def _normalize_tool_calls(raw: Any) -> list[dict]:
    """标准化 tool_calls 数据，确保 id/name/args 字段存在。"""
    if not raw:
        return []
    if not isinstance(raw, list):
        return []
    normalized = []
    for tc in raw:
        if isinstance(tc, dict):
            normalized.append({
                "id": tc.get("id", "") or tc.get("tool_call_id", ""),
                "name": tc.get("name", ""),
                "args": tc.get("args", {}) or tc.get("input", {}),
                "type": "tool_call",
            })
    return normalized


async def _astream_with_timeout(
    graph: CompiledStateGraph,
    state: AgentState,
    graph_config: dict[str, Any],
    timeout: float,
) -> AsyncGenerator[dict[str, Any], None]:
    """消费 LangGraph astream_events，单事件超时后触发 on_timeout。

    使用独立 consumer task + Queue 解耦超时与生成器消费，避免对同一个
    async generator 的 __anext__() 直接 wait_for/cancel 导致
    `anext(): asynchronous generator is already running`。
    """
    queue: asyncio.Queue[Any] = asyncio.Queue()
    agen = graph.astream_events(state, graph_config, version="v2")

    async def _consumer() -> None:
        try:
            async for event in agen:
                await queue.put(event)
            await queue.put(None)  # sentinel: done
        except Exception as exc:
            await queue.put(exc)

    consumer = asyncio.create_task(_consumer())
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                yield {
                    "event": "on_timeout",
                    "data": {"message": f"Agent 执行超时（{timeout}秒），请简化请求后重试"},
                }
                break

            if event is None:
                break
            if isinstance(event, Exception):
                raise event
            yield event
            queue.task_done()
    finally:
        consumer.cancel()
        try:
            await consumer
        except asyncio.CancelledError:
            pass
        await agen.aclose()


# 全局单例
agent_runner = AgentRunner()
