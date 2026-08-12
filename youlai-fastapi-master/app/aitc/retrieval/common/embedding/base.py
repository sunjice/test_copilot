"""Embedding provider 抽象基类与公共工具。

新增供应商流程（无需改动分发逻辑）：
1. 继承 EmbeddingProvider 实现 embed()
2. 在 __init__.py 中 register_provider("名称", 类) 注册
3. 配置侧新增对应字段并透传到 app/aitc/retrieval/common/config.py
之后 EMBEDDING_PROVIDER=名称 即可自由切换。
"""

import math
from abc import ABC, abstractmethod


def l2_normalize(vec: list[float]) -> list[float]:
    """L2 归一化，保证与 Milvus IP（内积）检索语义一致。"""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


class EmbeddingProvider(ABC):
    """向量化 provider 统一接口。"""

    name: str = "base"

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量文本 → 归一化向量列表（顺序与输入一致）。"""
        raise NotImplementedError
