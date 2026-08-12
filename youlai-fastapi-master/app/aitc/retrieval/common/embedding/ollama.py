"""Ollama 本地服务 provider。"""

import threading

import httpx
from loguru import logger

from app.aitc.retrieval.common.config import OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL
from app.aitc.retrieval.common.embedding.base import EmbeddingProvider, l2_normalize

_http_client: httpx.Client | None = None
_http_lock = threading.Lock()


class OllamaProvider(EmbeddingProvider):
    """本地 Ollama 服务：优先新版 /api/embed，404 时回退旧版 /api/embeddings。"""

    name = "ollama"

    def _client(self) -> httpx.Client:
        global _http_client
        if _http_client is not None:
            return _http_client

        with _http_lock:
            if _http_client is not None:
                return _http_client
            logger.info(f"Connecting to Ollama at {OLLAMA_BASE_URL}")
            _http_client = httpx.Client(base_url=OLLAMA_BASE_URL, timeout=60.0)
            return _http_client

    def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._client()
        try:
            resp = client.post(
                "/api/embed",
                json={"model": OLLAMA_EMBEDDING_MODEL, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings")
            if not embeddings:
                raise ValueError(f"Ollama /api/embed 响应缺少 embeddings: {data}")
            return [l2_normalize(v) for v in embeddings]
        except httpx.HTTPStatusError as exc:
            # 旧版本 Ollama 没有 /api/embed，回退到逐条 /api/embeddings
            if exc.response.status_code == 404:
                logger.warning("/api/embed 不可用，回退到旧版 /api/embeddings 逐条调用")
                return [self._embed_legacy(client, t) for t in texts]
            raise

    def _embed_legacy(self, client: httpx.Client, text: str) -> list[float]:
        resp = client.post(
            "/api/embeddings",
            json={"model": OLLAMA_EMBEDDING_MODEL, "prompt": text},
        )
        resp.raise_for_status()
        data = resp.json()
        emb = data.get("embedding")
        if not emb:
            raise ValueError(f"Ollama /api/embeddings 响应缺少 embedding: {data}")
        return l2_normalize(emb)
