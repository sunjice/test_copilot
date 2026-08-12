#!/usr/bin/env python3
"""全量同步用例数据到 Elasticsearch + Milvus（独立脚本，无需启动 FastAPI）。

用法:
    cd youlai-fastapi-master
    python scripts/sync_cases_to_engines.py

环境变量（可选覆盖默认值）:
    DATABASE_URL    - PostgreSQL 连接串
    ES_HOST         - Elasticsearch 地址
    MILVUS_HOST     - Milvus 地址
    MILVUS_PORT     - Milvus 端口
    EMBEDDING_DEVICE - cpu / cuda (默认 cpu)
"""

import asyncio
import os
import sys
import time

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _patch_config():
    """用环境变量或本地默认值覆盖远程配置（不修改 config.py）。"""
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://youlai:Youlai%402026@localhost:15432/youlai_admin",
    )
    os.environ.setdefault("ES_HOST", "http://localhost:9200")
    os.environ.setdefault("MILVUS_HOST", "localhost")
    os.environ.setdefault("MILVUS_PORT", "19530")
    os.environ.setdefault("EMBEDDING_DEVICE", "cpu")


_patch_config()

# 必须在 patch 之后再 import，确保 settings 读取到正确的环境变量
from app.config import settings  # noqa: E402
from app.database import AsyncSessionLocal  # noqa: E402
import app.aitc.models  # noqa: E402,F401  确保所有 ORM 模型已注册
from app.aitc.retrieval.case.indexer import reindex_all  # noqa: E402
from app.aitc.retrieval.common.client import close_es_client  # noqa: E402
from pymilvus import connections, utility  # noqa: E402
from loguru import logger  # noqa: E402


async def main():
    print("=" * 60)
    print(" 全量同步用例 → Elasticsearch + Milvus")
    print("=" * 60)
    print()
    print(f"  PostgreSQL : {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    print(f"  ES         : {settings.ES_HOST}")
    print(f"  Milvus     : {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
    print(f"  Embedding  : {settings.EMBEDDING_MODEL} ({settings.EMBEDDING_DEVICE})")
    print()

    # 1. 验证数据库连接
    print("[1/5] 验证 PostgreSQL 连接...")
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            result = await db.execute(text("SELECT count(*) FROM ai_tc_cases"))
            total = result.scalar()
            print(f"  用例总数: {total}")
            if total == 0:
                print("  [WARN] ai_tc_cases 表为空，无需同步")
                return
    except Exception as e:
        print(f"  [FATAL] 数据库连接失败: {e}")
        sys.exit(1)

    # 2. 验证 ES 连接
    print("[2/5] 验证 Elasticsearch 连接...")
    try:
        from elasticsearch import AsyncElasticsearch
        es = AsyncElasticsearch(hosts=[settings.ES_HOST])
        info = await es.info()
        print(f"  ES 版本: {info['version']['number']}")
        await es.close()
    except Exception as e:
        print(f"  [FATAL] ES 连接失败: {e}")
        sys.exit(1)

    # 3. 验证 Milvus 连接
    print("[3/5] 验证 Milvus 连接...")
    try:
        connections.connect(alias="sync", host=settings.MILVUS_HOST, port=str(settings.MILVUS_PORT))
        collections = utility.list_collections(using="sync")
        print(f"  已有 Collections: {collections}")
    except Exception as e:
        print(f"  [FATAL] Milvus 连接失败: {e}")
        sys.exit(1)

    # 4. 加载 Embedding 模型（首次会下载 ~1.3GB）
    print("[4/5] 加载 Embedding 模型...")
    try:
        from app.aitc.retrieval.common.client import get_embedding_model
        t0 = time.time()
        model = get_embedding_model()
        elapsed = time.time() - t0
        print(f"  模型已加载: {settings.EMBEDDING_MODEL} (耗时 {elapsed:.1f}s)")
    except Exception as e:
        print(f"  [FATAL] Embedding 模型加载失败: {e}")
        print("  如果是首次运行，可能需要下载模型文件 (~1.3GB)，请检查网络")
        sys.exit(1)

    # 5. 全量同步
    print(f"[5/5] 开始全量同步...")
    t0 = time.time()
    async with AsyncSessionLocal() as db:
        progress = await reindex_all(db)
    elapsed = time.time() - t0

    print()
    print("=" * 60)
    print(f"  总计: {progress.total}")
    print(f"  已索引: {progress.indexed}")
    print(f"  失败: {progress.failed}")
    print(f"  耗时: {elapsed:.1f}s")
    if progress.errors:
        print(f"  错误详情 (前10条):")
        for err in progress.errors[:10]:
            print(f"    - {err}")
    print("=" * 60)

    if progress.failed == 0:
        print("\n  全量同步完成!")
    else:
        print(f"\n  同步完成，但 {progress.failed} 条失败，请查看上方错误详情")

    # 清理
    await close_es_client()
    try:
        connections.disconnect("sync")
        connections.disconnect("default")
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
