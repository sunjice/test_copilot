"""本地 sentence-transformers 模型 provider。"""

import os
import threading
from pathlib import Path

from loguru import logger
from sentence_transformers import SentenceTransformer

from app.aitc.retrieval.common.config import EMBEDDING_DEVICE, EMBEDDING_DIM, EMBEDDING_MODEL
from app.aitc.retrieval.common.embedding.base import EmbeddingProvider

# 项目根目录（本文件位于 app/aitc/retrieval/common/embedding/，向上 5 级）
PROJECT_ROOT = Path(__file__).resolve().parents[5]

_local_model: SentenceTransformer | None = None
_local_lock = threading.Lock()


def _resolve_model_path(name: str) -> str:
    """解析模型路径：本地目录（绝对/相对项目根）优先，否则按 HF 模型名处理。"""
    if os.path.isabs(name) or os.path.isdir(name):
        return name
    local = PROJECT_ROOT / name
    if local.is_dir():
        return str(local)
    return name


class LocalProvider(EmbeddingProvider):
    """本地 sentence-transformers 模型（懒加载 + 线程安全，离线可用）。"""

    name = "local"

    def get_model(self) -> SentenceTransformer:
        global _local_model
        if _local_model is not None:
            return _local_model

        with _local_lock:
            if _local_model is not None:
                return _local_model
            model_path = _resolve_model_path(EMBEDDING_MODEL)
            logger.info(f"Loading local embedding model: {model_path}")
            # 本地模型目录时强制离线，避免联网下载超时
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            _local_model = SentenceTransformer(model_path, device=EMBEDDING_DEVICE)
            logger.info(f"Local embedding model loaded, dim={EMBEDDING_DIM}")
            return _local_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self.get_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return [e.tolist() for e in embeddings]
