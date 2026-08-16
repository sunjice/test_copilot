"""Chat Orchestrator — 对话编排器。

使用 LangChain 进行 LLM 调用和 Tool calling 编排。
当前实现按输入触发器选择策略，支持 Intent Skill、Agent、Freeform 三条路径。
"""

import hashlib
import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, AsyncGenerator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from loguru import logger

from app.ai.agent.skills.base import BaseSkill, SkillResult
from app.ai.agent.tools.base import ToolContext, tool_registry
from app.ai.chat.context_builder import context_builder_registry
from app.ai.chat.intent_router import intent_router
from app.ai.chat.session_manager import SessionContext
from app.ai.chat.usage_logger import LangChainTokenCallback, TokenMeter
from app.ai.config import ai_settings
from app.ai.llm_log.writer import LlmLogWriter


# ── prompt 模板缓存在模块级（只读一次磁盘） ──
_AGENT_PROMPT_TEMPLATE: str | None = None


def _get_agent_prompt_template() -> str:
    """加载 agent prompt 模板（模块级缓存，进程生命周期内只读一次磁盘）。"""
    global _AGENT_PROMPT_TEMPLATE
    if _AGENT_PROMPT_TEMPLATE is None:
        prompt_path = Path(__file__).parent.parent / "agent" / "prompts" / "agent_case.txt"
        try:
            _AGENT_PROMPT_TEMPLATE = prompt_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            _AGENT_PROMPT_TEMPLATE = SYSTEM_PROMPT
    return _AGENT_PROMPT_TEMPLATE


# 系统提示词 — 自由对话模式
SYSTEM_PROMPT = """你是测试部的 AI 助手，专注于帮助测试工程师管理测试用例。

## 你的能力
你可以帮助用户：
1. **挑选核心用例** — 从项目用例中智能挑选最核心的测试用例
2. **审核用例质量** — 检查用例的完整性、规范性、可执行性
3. **生成测试脚本** — 为用例自动生成 pytest 自动化测试脚本
4. **补全用例字段** — 根据标题和测试目的，补全前置条件、测试数据等
5. **补写测试步骤** — 补写详细的测试步骤和预期结果
6. **设计测试用例** — 根据需求描述，从零设计测试用例

## 交互原则
- 回复简洁专业，优先引导用户使用具体技能
- 需要项目/用例信息时，优先使用 [当前页面上下文] 中已提供的数据；如上下文不足，再主动询问
- 涉及数据修改时，先生成确认卡片等用户确认
- 数学计算、代码片段使用 Markdown 格式
"""


class PromptManager:
    """统一管理 AI prompt 与上下文构造。"""

    async def build_context_block(self, context: SessionContext) -> str:
        builder = context_builder_registry.get(context.domain)
        if builder is None:
            return ""
        db = context.get_working("db_session")
        if db is None:
            return ""
        return await builder.build(context.context_json, db)

    def build_agent_prompt(self, context: SessionContext, tools: list[BaseTool]) -> str:
        prompt = _get_agent_prompt_template()
        prompt += self._build_page_context(context)
        # 工具定义已通过 create_react_agent 的 tools 参数传入 API，
        # 不再需要拼到 system prompt 文本中，避免重复浪费 token。
        # prompt += self._build_tools_prompt(tools)
        return prompt

    async def build_freeform_messages(
        self,
        context: SessionContext,
        history: list[dict] | None,
        message: str,
    ) -> tuple[list[BaseMessage], str]:
        messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
        fingerprint = self._compute_fingerprint(context.domain, context.context_json)
        if fingerprint and fingerprint != context.last_context_fingerprint:
            context_block = await self.build_context_block(context)
            if context_block:
                messages.append(SystemMessage(content=context_block))
        if history:
            for h in history[-20:]:
                if h.get("role") == "user":
                    messages.append(HumanMessage(content=h.get("content", "")))
                elif h.get("role") == "assistant":
                    messages.append(AIMessage(content=h.get("content", "")))
        messages.append(HumanMessage(content=message))
        return messages, fingerprint

    def _build_page_context(self, context: SessionContext) -> str:
        project_id = context.project_id
        suite_id = context.suite_id
        project_name = context.context_json.get("project_name", "")
        suite_name = context.context_json.get("suite_name", "")
        selected_case_ids = context.context_json.get("selected_case_ids", [])
        current_case_id = context.context_json.get("current_case_id")

        lines = ["\n\n## 当前页面上下文"]
        if project_id:
            name_part = f" {project_name}" if project_name else ""
            lines.append(f"- 项目：{project_id}{name_part}")
        if suite_id:
            name_part = f" {suite_name}" if suite_name else ""
            lines.append(f"- 模块：{suite_id}{name_part}")
        if current_case_id:
            lines.append(f"- 当前查看的用例 ID：{current_case_id}")
        if selected_case_ids:
            ids_str = ", ".join(str(i) for i in selected_case_ids[:20])
            suffix = f" 等共 {len(selected_case_ids)} 条" if len(selected_case_ids) > 20 else f"（共 {len(selected_case_ids)} 条）"
            lines.append(f"- 已选中的用例 ID：{ids_str}{suffix}")

        if len(lines) == 1:
            return ""

        lines.append("")
        lines.append("注意：如果用户有选中用例（selected_case_ids），可优先作为操作对象。但如果用户明确要求对整个模块操作，以用户意图为准。")
        return "\n".join(lines)

    def _build_tools_prompt(self, tools: list[BaseTool]) -> str:
        if not tools:
            return ""
        try:
            from app.ai.agent.tools.case import generate_tools_prompt

            return "\n\n" + generate_tools_prompt(tools)
        except Exception:
            return ""

    @staticmethod
    def _compute_fingerprint(domain: str, context_json: dict) -> str:
        if not context_json:
            return ""
        raw = f"{domain}:{json.dumps(context_json, sort_keys=True, default=str)}"
        return hashlib.md5(raw.encode()).hexdigest()


class ChatStrategy(ABC):
    @abstractmethod
    async def handle(
        self,
        message: str,
        context: SessionContext,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        ...


class FreeformStrategy(ChatStrategy):
    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager

    async def handle(
        self,
        message: str,
        context: SessionContext,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        ai_config = context.get_working("ai_config")
        if ai_config is None:
            yield {"event": "message", "data": {
                "role": "assistant",
                "msg_type": "text",
                "content": "未配置 AI 服务，请在 .env 中设置 AI_API_KEY 等参数。",
            }}
            yield {"event": "done", "data": {}}
            return

        meter = TokenMeter(model=ai_config.model or "unknown")
        t_start = time.time()

        messages_raw: list[dict] = []
        try:
            messages, fingerprint = await self.prompt_manager.build_freeform_messages(context, history, message)
            if fingerprint and fingerprint != context.last_context_fingerprint:
                context.last_context_fingerprint = fingerprint

            messages_raw = _serialize_messages(messages)
            llm = ChatOpenAI(
                model=ai_config.model,
                api_key=ai_config.api_key,
                base_url=ai_config.api_base,
                temperature=ai_config.temperature or 0.3,
                max_tokens=ai_config.max_tokens or 4096,
                streaming=True,
            )
            callback = LangChainTokenCallback(meter)
            full_text = ""

            logger.debug("[FreeformStrategy] LLM astream 开始")
            chunk_count = 0
            async for chunk in llm.astream(messages, config={"callbacks": [callback]}):
                if chunk.content:
                    full_text += chunk.content
                    chunk_count += 1
                    yield {"event": "chunk", "data": {"content": chunk.content}}
            logger.debug(f"[FreeformStrategy] LLM astream 完成 chunks={chunk_count}")

            duration_ms = int((time.time() - t_start) * 1000)
            await LlmLogWriter.write(
                session_id=context.session_id,
                message_id=context.get_working("message_id"),
                seq=0,
                event_type="llm_call",
                module="chat",
                action="freeform_chat",
                provider=ai_config.provider,
                api_base=ai_config.api_base,
                model=ai_config.model or "unknown",
                status="success",
                request_messages=messages_raw,
                response_raw=full_text,
                prompt_tokens=meter.prompt_tokens,
                completion_tokens=meter.completion_tokens,
                duration_ms=duration_ms,
            )

            yield {"event": "message", "data": {
                "role": "assistant",
                "msg_type": "text",
                "content": full_text,
                "metadata": {
                    "tokens": {
                        "prompt": meter.prompt_tokens,
                        "completion": meter.completion_tokens,
                        "total": meter.total_tokens,
                    },
                    "duration_ms": duration_ms,
                },
            }}
            yield {"event": "done", "data": {}}

        except Exception as e:
            duration_ms = int((time.time() - t_start) * 1000)
            await LlmLogWriter.write(
                session_id=context.session_id,
                message_id=context.get_working("message_id"),
                seq=0,
                event_type="llm_call",
                module="chat",
                action="freeform_chat",
                provider=ai_config.provider if ai_config else "unknown",
                api_base=ai_config.api_base if ai_config else "",
                model=ai_config.model if ai_config else "unknown",
                status="error",
                error_msg=str(e)[:500],
                request_messages=messages_raw if messages_raw else None,
                prompt_tokens=meter.prompt_tokens,
                completion_tokens=meter.completion_tokens,
                duration_ms=duration_ms,
            )
            yield {"event": "error", "data": {"message": str(e)}}
            yield {"event": "done", "data": {}}


class IntentRoutingStrategy(ChatStrategy):
    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager

    async def handle(
        self,
        message: str,
        context: SessionContext,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        skill, clean_message = self._resolve_skill_from_command(message, context.domain)
        if skill is None:
            skill = intent_router.match(message, domain=context.domain)
        if skill is None:
            async for event in FreeformStrategy(self.prompt_manager).handle(message, context, history):
                yield event
            return

        params = intent_router.extract_params(skill, clean_message or message)
        params["project_id"] = params.get("project_id") or context.project_id
        params["suite_id"] = params.get("suite_id") or context.suite_id
        current_page = context.context_json.get("current_page", "")

        if skill.required_page and current_page != skill.required_page:
            result = SkillResult(
                success=False,
                msg_type="clarify_card",
                content="该功能需要在「用例管理」页面使用。请先切换到用例管理页面，再进行此操作。",
            )
        else:
            result = await skill.execute(params, {
                "session_id": context.session_id,
                "project_id": context.project_id,
                "suite_id": context.suite_id,
                "domain": context.domain,
                "context_json": context.context_json,
                "db_session": context.get_working("db_session"),
            })

        yield {"event": "skill_start", "data": {
            "skill_name": skill.name,
            "mode": skill.mode.value,
        }}

        # 统一到 parts 体系：skill 执行作为一个 tool part，
        # 卡片结果（confirm_card/clarify_card）作为对应 part 内嵌进单条 message。
        t0 = time.time()
        run_id = f"skill-{skill.name}-{int(t0 * 1000)}"

        # 1) tool_start：skill 执行开始
        yield {"event": "tool_start", "data": {
            "name": skill.name,
            "run_id": run_id,
            "args": {},
        }}

        # 2) 构造 parts（tool + 文本/卡片），与 agent 路径格式一致
        duration_ms = int((time.time() - t0) * 1000)
        parts: list[dict] = [
            {
                "type": "tool",
                "id": run_id,
                "name": skill.name,
                "status": "done",
                "durationMs": duration_ms,
            },
        ]
        if result.msg_type in ("confirm_card", "clarify_card", "task_card"):
            card_data = dict(result.metadata or {})
            card_data["content"] = result.content
            card_data["msg_type"] = result.msg_type
            card_data["skill_name"] = skill.name
            parts.append({"type": result.msg_type, "card": card_data})
        else:
            if result.content:
                parts.append({"type": "text", "content": result.content})

        # 3) tool_end：skill 执行结束（结算 tool part 的 durationMs）
        yield {"event": "tool_end", "data": {
            "name": skill.name,
            "run_id": run_id,
            "durationMs": duration_ms,
        }}

        # 4) 单条 message，parts 内嵌（text + 卡片），与 agent 路径格式一致
        metadata = dict(result.metadata or {})
        metadata["parts"] = parts
        metadata["skill_name"] = skill.name
        metadata["tool_names"] = [skill.name]
        metadata["tool_calls"] = 1
        metadata["duration_ms"] = duration_ms

        yield {"event": "message", "data": {
            "role": "assistant",
            "msg_type": "text",
            "content": result.content if result.msg_type not in ("confirm_card", "clarify_card", "task_card") else "",
            "skill_name": skill.name,
            "success": result.success,
            "metadata": metadata,
        }}

        if result.error and not result.content:
            yield {"event": "error", "data": {"message": result.error}}

        yield {"event": "done", "data": {}}

    def _resolve_skill_from_command(self, message: str, domain: str) -> tuple[BaseSkill | None, str | None]:
        """支持 /skill_name 或 /domain skill_name 命令触发技能。"""
        text = message.strip()
        if not text.startswith("/"):
            return None, None

        parts = text[1:].split(None, 2)
        if not parts:
            return None, None

        if len(parts) == 1:
            candidate = parts[0].strip()
            remainder = ""
        elif len(parts) == 2:
            candidate = parts[0].strip()
            remainder = parts[1].strip()
        else:
            candidate = parts[0].strip()
            remainder = parts[1] + " " + parts[2]

        # 支持 /domain skill_name 形式
        if candidate in {"case", "bug", "exec", "project"} and remainder:
            skill_name = remainder.split(None, 1)[0]
            cmd_text = remainder[len(skill_name):].strip()
        else:
            skill_name = candidate
            cmd_text = remainder

        from app.ai.agent.skills.base import skill_registry
        skill = skill_registry.get(skill_name)
        if skill is None:
            return None, None
        return skill, cmd_text


class AgentExecutor:
    async def run(
        self,
        message: str,
        context: SessionContext,
        history: list[dict] | None,
        tools: list[BaseTool],
        system_prompt: str,
        ai_config: Any,
    ) -> AsyncGenerator[dict, None]:
        from app.ai.agent.graph.runner import agent_runner

        async for raw_event in agent_runner.run(
            message=message,
            context=context,
            history=history,
            tools=tools,
            system_prompt=system_prompt,
            ai_config=ai_config,
        ):
            yield self._parse_sse(raw_event)

    @staticmethod
    def _parse_sse(raw: str) -> dict:
        event_name = "message"
        data: dict[str, Any] = {}
        for line in raw.splitlines():
            if line.startswith("event: "):
                event_name = line[7:].strip()
            elif line.startswith("data: "):
                payload = line[6:].strip()
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    data = {"raw": payload}
        return {"event": event_name, "data": data}


class AgentStrategy(ChatStrategy):
    def __init__(self, prompt_manager: PromptManager, executor: AgentExecutor):
        self.prompt_manager = prompt_manager
        self.executor = executor

    async def handle(
        self,
        message: str,
        context: SessionContext,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        ai_config = context.get_working("ai_config")
        db = context.get_working("db_session")
        if ai_config is None:
            yield {"event": "message", "data": {
                "role": "assistant",
                "msg_type": "text",
                "content": "未配置 AI 服务，请在 .env 中设置 AI_API_KEY 等参数。",
            }}
            yield {"event": "done", "data": {}}
            return

        from app.ai.agent.tools.case import build_case_tools  # ensure case domain builder is registered

        tool_ctx = ToolContext(
            db=db,
            session_id=context.session_id,
            domain=context.domain,
            page_type=context.context_json.get("current_page", ""),
            context_json=context.context_json,
            user_id=context.context_json.get("user_id") or 0,
        )
        tools = tool_registry.build_tools(context.domain, tool_ctx)
        if not tools and context.domain == "case":
            tools = build_case_tools(tool_ctx)
        system_prompt = self.prompt_manager.build_agent_prompt(context, tools)

        async for event in self.executor.run(
            message=message,
            context=context,
            history=history,
            tools=tools,
            system_prompt=system_prompt,
            ai_config=ai_config,
        ):
            yield event


class TriggerRouter:
    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager

    def route(self, message: str, context: SessionContext) -> ChatStrategy:
        text = message.strip()
        if text.startswith("/"):
            return IntentRoutingStrategy(self.prompt_manager)
        if text.startswith("@"):
            return AgentStrategy(self.prompt_manager, AgentExecutor())
        if ai_settings.AI_AGENT_MODE_ENABLED and context.domain == "case":
            return AgentStrategy(self.prompt_manager, AgentExecutor())
        return IntentRoutingStrategy(self.prompt_manager)


class ChatOrchestrator:
    """对话编排器 — 负责意图识别 → Skill/Agent/Freeform 策略选择与调度。"""

    def __init__(self):
        self._prompt_manager = PromptManager()
        self._trigger_router = TriggerRouter(self._prompt_manager)

    async def process_message(
        self,
        message: str,
        context: SessionContext,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        logger.debug("[ChatOrchestrator.process_message] START")
        t0 = time.time()
        strategy = self._trigger_router.route(message, context)
        event_count = 0
        try:
            async for event in strategy.handle(message, context, history):
                yield self._sse_event(event["event"], event["data"])
                event_count += 1
        finally:
            dt = int((time.time() - t0) * 1000)
            logger.debug(f"[ChatOrchestrator.process_message] END 耗时={dt}ms events={event_count}")

    @staticmethod
    def _sse_event(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# 全局单例
chat_orchestrator = ChatOrchestrator()


def _serialize_messages(messages: list[BaseMessage]) -> list[dict]:
    """将 LangChain BaseMessage 列表序列化为普通 dict 列表，用于存储日志。"""
    result = []
    for m in messages:
        role_map = {
            "system": "system", "human": "user", "ai": "assistant",
            "tool": "tool", "function": "function",
        }
        role = role_map.get(m.type, m.type)
        entry = {"role": role, "content": m.content}
        if hasattr(m, "tool_calls") and m.tool_calls:
            entry["tool_calls"] = [tc.model_dump() if hasattr(tc, "model_dump") else str(tc) for tc in m.tool_calls]
        if hasattr(m, "name") and m.name:
            entry["name"] = m.name
        result.append(entry)
    return result
