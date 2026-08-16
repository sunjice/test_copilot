"""AI 平台配置 — 从 .env / 环境变量读取，替代旧的 DB 端 aiconfig 管理。

所有 AI 相关配置均从此模块读取。环境变量名以 AI_ 为前缀，与 app/config.py 的
Settings 自动合并（pydantic-settings case_sensitive=False）。"""

from dataclasses import dataclass

from pydantic_settings import BaseSettings, SettingsConfigDict


class AiSettings(BaseSettings):
    """AI 专用配置，均可通过 .env 或环境变量覆盖。"""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 默认 AI 连接 ──
    AI_API_BASE: str = "https://api.deepseek.com"
    AI_API_KEY: str = ""
    AI_MODEL: str = "deepseek-chat"
    AI_TEMPERATURE: float = 0.3
    AI_MAX_TOKENS: int = 4096

    # ── 批次控制 ──
    AI_BATCH_SIZE: int = 30          # 每批处理用例数
    AI_MAX_CONCURRENT: int = 3       # 最大并发 LLM 调用

    # ── 按场景覆盖（预留） ──
    AI_CORE_SELECT_MODEL: str = ""   # 核心挑选专用模型，为空则用 AI_MODEL
    AI_CASE_REVIEW_MODEL: str = ""   # 用例审核专用模型
    AI_SCRIPT_GEN_MODEL: str = ""    # 脚本生成专用模型

    # ── Agent 模式开关 ──
    AI_AGENT_MODE_ENABLED: bool = True  # 开启后，用例域对话走 LangGraph agent 模式


ai_settings = AiSettings()


# ═══════════════ AiConfigSnapshot + resolve_ai_config ═══════════════

@dataclass
class AiConfigSnapshot:
    """AI 配置快照（替代旧的 AiTcAiConfig 模型）。"""
    model: str
    api_base: str
    api_key: str
    temperature: float
    max_tokens: int
    id: int | None = None  # 保留字段，兼容旧代码

    @property
    def provider(self) -> str:
        """从 api_base 推断供应商，用于费用统计与日志区分。"""
        return infer_provider(self.api_base)


def infer_provider(api_base: str) -> str:
    """从接口地址推断供应商标识：deepseek / openai / local / unknown。"""
    base = (api_base or "").lower()
    if "deepseek" in base:
        return "deepseek"
    if "openai" in base:
        return "openai"
    if "localhost" in base or "127.0.0.1" in base or "ollama" in base:
        return "local"
    return "unknown"


def resolve_ai_config(scene: str = "chat") -> AiConfigSnapshot:
    """解析 AI 配置：统一从 .env 读取（不再查询 DB aiconfig 表）。

    Parameters
    ----------
    scene : str
        调用场景：chat / core_select / case_review / script_gen。
        会按场景选择专用模型（如 AI_CORE_SELECT_MODEL），未配置则用 AI_MODEL。
    """
    scene_model_map = {
        "core_select": ai_settings.AI_CORE_SELECT_MODEL,
        "case_review": ai_settings.AI_CASE_REVIEW_MODEL,
        "script_gen": ai_settings.AI_SCRIPT_GEN_MODEL,
    }
    model = scene_model_map.get(scene) or ai_settings.AI_MODEL
    return AiConfigSnapshot(
        model=model,
        api_base=ai_settings.AI_API_BASE,
        api_key=ai_settings.AI_API_KEY,
        temperature=ai_settings.AI_TEMPERATURE,
        max_tokens=ai_settings.AI_MAX_TOKENS,
    )
