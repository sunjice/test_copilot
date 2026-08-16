"""AI 客户端 — 统一 OpenAI 兼容接口封装，配置从 .env / AiConfigSnapshot 读取。

职责边界：仅负责底层 AI 交互（chat_json + JSON 解析 + token 统计）。
任务相关的 prompt 构建、结果解析、业务逻辑已迁移到 tasks/ 目录下各任务文件。
"""

import json
import re
import time
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from app.ai.llm_log.writer import LlmLogWriter


class AiClient:
    """OpenAI 兼容异步客户端，支持 DeepSeek / OpenAI / 其他兼容 provider。

    用法:
        from app.ai.config import AiConfigSnapshot
        config = AiConfigSnapshot(model="...", api_base="...", api_key="...", temperature=0.3, max_tokens=4096)
        client = AiClient(config)
        result = await client.chat_json(system_prompt, user_prompt)
    """

    def __init__(self, ai_config: Any):
        """ai_config: AiConfigSnapshot 实例，如果为 None 则使用 .env 兜底。"""
        if ai_config is None:
            from app.ai.config import ai_settings
            self.api_base = ai_settings.AI_API_BASE
            self.api_key = ai_settings.AI_API_KEY
            self.model = ai_settings.AI_MODEL
            self.temperature = ai_settings.AI_TEMPERATURE
            self.max_tokens = ai_settings.AI_MAX_TOKENS
        else:
            self.api_base = ai_config.api_base
            self.api_key = ai_config.api_key
            self.model = ai_config.model
            self.temperature = ai_config.temperature if ai_config.temperature is not None else 0.3
            self.max_tokens = ai_config.max_tokens if ai_config.max_tokens is not None else 4096

        # 标准 OpenAI SDK 写法：api_key + base_url，SDK 自动处理鉴权
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=120.0,
            max_retries=1,
        )
        # Token 用量累计
        self.input_tokens = 0
        self.output_tokens = 0

        # ── 日志上下文（由调用方 set_log_context 设置）──
        self._log_action: str = ""
        self._log_module: str = "task_engine"
        self._log_session_id: int | None = None
        self._log_task_id: int | None = None
        self._log_message_id: int | None = None
        self._log_provider: str = ""
        self._log_seq: int = 0

    def set_log_context(
        self,
        *,
        action: str = "",
        module: str = "task_engine",
        session_id: int | None = None,
        task_id: int | None = None,
        message_id: int | None = None,
        provider: str = "",
    ):
        """设置 LLM 调用日志上下文。每次 chat_json 调用自动写入 ai_run_events。"""
        self._log_action = action
        self._log_module = module
        self._log_session_id = session_id
        self._log_task_id = task_id
        self._log_message_id = message_id
        self._log_provider = provider
        self._log_seq = 0

    # ── 底层调用 ──

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        retry: int = 1,
    ) -> dict | list:
        """发送 Chat Completion 请求，返回解析后的 JSON（优先 JSON Mode，失败则正则兜底解析 + 重试）。
        每次调用自动写入 ai_run_events 审计日志。
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        seq = self._log_seq
        self._log_seq += 1

        for attempt in range(retry + 1):
            t_start = time.time()
            try:
                # 优先使用 JSON Mode（部分 provider 不支持，失败降级）
                try:
                    resp = await self._client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temp,
                        max_tokens=max_tok,
                        response_format={"type": "json_object"},
                    )
                except Exception:
                    # JSON Mode 不支持时降级为普通模式
                    resp = await self._client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temp,
                        max_tokens=max_tok,
                    )

                text = resp.choices[0].message.content or ""
                parsed = self._extract_json(text)
                duration_ms = int((time.time() - t_start) * 1000)
                usage = resp.usage
                prompt_tok = usage.prompt_tokens if usage else 0
                completion_tok = usage.completion_tokens if usage else 0
                cache_hit = self._usage_getattr(usage, "prompt_cache_hit_tokens")
                cache_miss = self._usage_getattr(usage, "prompt_cache_miss_tokens")
                cache_write = self._usage_getattr(usage, "prompt_cache_write_tokens")
                reasoning = self._usage_getattr(
                    getattr(usage, "completion_tokens_details", None), "reasoning_tokens"
                )

                if parsed is not None:
                    self.input_tokens += prompt_tok
                    self.output_tokens += completion_tok
                    logger.debug(f"AI response parsed successfully, tokens: in={prompt_tok} out={completion_tok}")

                    # ── 写入成功日志 ──
                    await self._write_log(
                        seq=seq, attempt=attempt,
                        messages=messages, response_raw=text,
                        response_json=parsed,
                        prompt_tokens=prompt_tok,
                        prompt_cache_hit_tokens=cache_hit,
                        prompt_cache_miss_tokens=cache_miss,
                        prompt_cache_write_tokens=cache_write,
                        completion_tokens=completion_tok,
                        reasoning_tokens=reasoning,
                        duration_ms=duration_ms,
                        status="success",
                    )
                    return parsed

                if attempt < retry:
                    logger.warning(f"JSON parse failed, retry {attempt + 1}/{retry}. Raw: {text[:200]}")
                    messages.append({"role": "user", "content": "请严格按照 JSON 格式输出，不要包含任何多余的文字。"})
                else:
                    logger.error(f"JSON parse failed after {retry + 1} attempts. Raw: {text[:500]}")
                    # ── 写入失败日志（解析失败）──
                    await self._write_log(
                        seq=seq, attempt=attempt,
                        messages=messages, response_raw=text,
                        prompt_tokens=prompt_tok,
                        prompt_cache_hit_tokens=cache_hit,
                        prompt_cache_miss_tokens=cache_miss,
                        prompt_cache_write_tokens=cache_write,
                        completion_tokens=completion_tok,
                        reasoning_tokens=reasoning,
                        duration_ms=duration_ms,
                        status="error",
                        error_msg=f"JSON解析失败，原始返回: {text[:200]}",
                    )

            except Exception as e:
                duration_ms = int((time.time() - t_start) * 1000)
                logger.error(f"AI API call error (attempt {attempt + 1}): {e}")
                await self._write_log(
                    seq=seq, attempt=attempt,
                    messages=messages,
                    duration_ms=duration_ms,
                    status="error",
                    error_msg=str(e)[:500],
                )
                if attempt >= retry:
                    raise

        return {}  # fallback

    @staticmethod
    def _usage_getattr(obj: Any, name: str) -> int:
        """安全读取 usage 子字段，缺失时返回 0（兼容不同 provider 的字段差异）。"""
        try:
            val = getattr(obj, name, None)
            return int(val) if val is not None else 0
        except (TypeError, ValueError):
            return 0

    # ── 日志写入 ──

    async def _write_log(
        self,
        *,
        seq: int,
        attempt: int,
        messages: list[dict],
        response_raw: str | None = None,
        response_json: dict | list | None = None,
        prompt_tokens: int = 0,
        prompt_cache_hit_tokens: int = 0,
        prompt_cache_miss_tokens: int = 0,
        prompt_cache_write_tokens: int = 0,
        completion_tokens: int = 0,
        reasoning_tokens: int = 0,
        duration_ms: int = 0,
        status: str = "success",
        error_msg: str | None = None,
    ):
        """异步写入 ai_run_events 表。"""
        if not self._log_action:
            return  # 未设置日志上下文，跳过
        await LlmLogWriter.write(
            session_id=self._log_session_id,
            message_id=self._log_message_id,
            seq=seq,
            event_type="llm_call",
            module=self._log_module,
            action=self._log_action,
            provider=self._log_provider,
            api_base=self.api_base,
            model=self.model,
            status=status,
            error_msg=error_msg,
            request_messages=messages,
            response_raw=response_raw,
            response_json=response_json,
            prompt_tokens=prompt_tokens,
            prompt_cache_hit_tokens=prompt_cache_hit_tokens,
            prompt_cache_miss_tokens=prompt_cache_miss_tokens,
            prompt_cache_write_tokens=prompt_cache_write_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens,
            duration_ms=duration_ms,
        )

    # ── JSON 解析 ──

    @staticmethod
    def _extract_json(text: str) -> dict | list | None:
        """从 AI 返回文本中提取 JSON，优先直接解析，失败则正则提取。"""
        text = text.strip()
        # 1) 直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2) 提取 ```json ... ``` 代码块
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 3) 提取首对 {} 或 []
        m = re.search(r"(\{[\s\S]*?\}|\[[\s\S]*?\])", text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass

        return None
