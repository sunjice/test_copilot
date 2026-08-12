"""OpenAI 兼容 Embeddings API provider。

OpenAI 官方 / 通义千问（DashScope）/ DeepSeek 等均提供 OpenAI 兼容的 /embeddings
接口，统一由 OpenAIProvider 支持；Azure OpenAI 是端点格式不同（/openai/deployments/...）
的特例，由 AzureProvider 支持。二者共用 OpenAICompatProvider 的调用与排序逻辑。
"""

import threading

from loguru import logger
from openai import AzureOpenAI, OpenAI

from app.aitc.retrieval.common.config import (
    AZURE_EMBEDDING_DEPLOYMENT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_ENDPOINT,
    OPENAI_EMBEDDING_API_KEY,
    OPENAI_EMBEDDING_BASE_URL,
    OPENAI_EMBEDDING_MODEL,
)
from app.aitc.retrieval.common.embedding.base import EmbeddingProvider, l2_normalize

_client_cache: dict[str, object] = {}
_client_lock = threading.Lock()


class OpenAICompatProvider(EmbeddingProvider):
    """OpenAI 兼容 Embeddings API 基类。

    子类只需实现 _build_client()（客户端构造）与 _model()（部署名/模型名）。
    """

    name = "openai_compat"

    def _build_client(self) -> object:
        raise NotImplementedError

    def _model(self) -> str:
        raise NotImplementedError

    def _get_client(self) -> object:
        key = self.name
        if key in _client_cache:
            return _client_cache[key]
        with _client_lock:
            if key not in _client_cache:
                _client_cache[key] = self._build_client()
            return _client_cache[key]

    def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        resp = client.embeddings.create(model=self._model(), input=texts)
        # 结果按 index 排序，保证与输入顺序一致
        ordered = sorted(resp.data, key=lambda d: d.index)
        return [l2_normalize(d.embedding) for d in ordered]


class OpenAIProvider(OpenAICompatProvider):
    """OpenAI 官方 / 通义千问 / DeepSeek 等 OpenAI 兼容端点（EMBEDDING_PROVIDER=openai）。"""

    name = "openai"

    def _build_client(self) -> OpenAI:
        if not OPENAI_EMBEDDING_API_KEY:
            raise RuntimeError(
                "OpenAI 兼容 Embedding 未配置：请设置 OPENAI_EMBEDDING_API_KEY\n"
                "  - 通义千问（DashScope）：OPENAI_EMBEDDING_BASE_URL="
                "https://dashscope.aliyuncs.com/compatible-mode/v1\n"
                "  - OpenAI 官方：OPENAI_EMBEDDING_BASE_URL 留空"
            )
        logger.info(
            f"OpenAI 兼容 Embedding: model={OPENAI_EMBEDDING_MODEL}, "
            f"base_url={OPENAI_EMBEDDING_BASE_URL or '<官方>'}"
        )
        return OpenAI(
            api_key=OPENAI_EMBEDDING_API_KEY,
            base_url=OPENAI_EMBEDDING_BASE_URL or None,
        )

    def _model(self) -> str:
        return OPENAI_EMBEDDING_MODEL


class AzureProvider(OpenAICompatProvider):
    """Azure OpenAI Embeddings（EMBEDDING_PROVIDER=azure）。"""

    name = "azure"

    def _build_client(self) -> AzureOpenAI:
        if not AZURE_OPENAI_API_KEY or "your-resource" in AZURE_OPENAI_ENDPOINT:
            raise RuntimeError(
                "Azure Embedding 未配置：请设置 AZURE_OPENAI_API_KEY 和 AZURE_OPENAI_ENDPOINT"
            )
        logger.info(
            f"Azure Embedding: endpoint={AZURE_OPENAI_ENDPOINT}, "
            f"deployment={AZURE_EMBEDDING_DEPLOYMENT}"
        )
        return AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
        )

    def _model(self) -> str:
        return AZURE_EMBEDDING_DEPLOYMENT
