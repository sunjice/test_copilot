"""Embedding provider 注册表与统一入口。

通过配置 EMBEDDING_PROVIDER 切换向量化供应商，内置：
- local：本地 sentence-transformers 模型
- ollama：本地 Ollama 服务
- openai：OpenAI 兼容端点（通义千问 / DeepSeek / OpenAI 官方等）
- azure：Azure OpenAI

扩展新供应商（无需改动任何分发代码）：
1. 新增 provider 类，继承 app.aitc.retrieval.common.embedding.base.EmbeddingProvider
2. 调用 register_provider("名称", 类) 注册
3. 配置侧新增对应字段并透传到 common/config.py
"""

from typing import Any

from app.aitc.retrieval.common.config import EMBEDDING_PROVIDER

from .base import EmbeddingProvider
from .local import LocalProvider
from .ollama import OllamaProvider
from .openai_compat import AzureProvider, OpenAIProvider

_REGISTRY: dict[str, type[EmbeddingProvider]] = {
    "local": LocalProvider,
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "azure": AzureProvider,
}


def register_provider(name: str, cls: type[EmbeddingProvider]) -> None:
    """注册自定义 provider（名称小写存储，覆盖同名字段）。"""
    _REGISTRY[name.strip().lower()] = cls


def get_provider(name: str | None = None) -> EmbeddingProvider:
    """按名称获取 provider 实例（默认取配置 EMBEDDING_PROVIDER）。"""
    key = (name or EMBEDDING_PROVIDER or "local").strip().lower()
    cls = _REGISTRY.get(key)
    if cls is None:
        raise ValueError(
            f"未知 EMBEDDING_PROVIDER: {key!r}，可选: {', '.join(sorted(_REGISTRY))}"
        )
    return cls()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量文本 → 向量（同步调用，需在 async 中用 run_in_executor）。"""
    return get_provider().embed(texts)


def get_embedding_model() -> Any:
    """兼容别名：返回本地 sentence-transformers 模型（脚本批量同步用）。"""
    return LocalProvider().get_model()
