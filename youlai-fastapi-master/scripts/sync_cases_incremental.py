#!/usr/bin/env python3
"""增量同步用例到 Elasticsearch + Milvus（运维入口，无需启动 FastAPI）。

用法:
    cd youlai-fastapi-master
    # 增量同步全部用例（内容未变自动跳过）
    python scripts/sync_cases_incremental.py
    # 指定用例增量索引（例如新增/修改后只补这几条）
    python scripts/sync_cases_incremental.py --case-ids 101,102,103

环境变量（可选覆盖默认值）:
    DATABASE_URL    - PostgreSQL 连接串
    ES_HOST         - Elasticsearch 地址
    MILVUS_HOST     - Milvus 地址
    MILVUS_PORT     - Milvus 端口
    EMBEDDING_DEVICE - cpu / cuda (默认 cpu)
"""

import argparse
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


def _parse_args():
    parser = argparse.ArgumentParser(description="增量同步用例到 ES + Milvus")
    parser.add_argument(
        "--case-ids",
        type=str,
        default=None,
        help="指定用例 ID 列表（逗号分隔），不传则增量同步全部用例",
    )
    return parser.parse_args()


_patch_config()

# 必须在 patch 之后再 import，确保 settings 读取到正确的环境变量
from app.config import settings  # noqa: E402
from app.database import AsyncSessionLocal  # noqa: E402
import app.aitc.models  # noqa: E402,F401  确保所有 ORM 模型已注册
from app.aitc.retrieval.case.indexer import index_batch  # noqa: E402
from app.aitc.retrieval.case.schemas import IndexProgress  # noqa: E402
from app.aitc.case.models import AiTcCase  # noqa: E402
from sqlalchemy import select  # noqa: E402
from loguru import logger  # noqa: E402


async def main():
    args = _parse_args()
    print("=" * 60)
    print(" 增量同步用例 → Elasticsearch + Milvus")
    print("=" * 60)
    print(f"  ES={settings.ES_HOST}  Milvus={settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
    print()

    async with AsyncSessionLocal() as db:
        # 1. 确定待同步用例
        if args.case_ids:
            try:
                case_ids = [int(x.strip()) for x in args.case_ids.split(",") if x.strip()]
            except ValueError as e:
                print(f"  [FATAL] --case-ids 参数非法: {e}")
                sys.exit(1)
            print(f"[1/3] 指定用例: {len(case_ids)} 条")
        else:
            result = await db.execute(select(AiTcCase.id).order_by(AiTcCase.id))
            case_ids = [row[0] for row in result.fetchall()]
            print(f"[1/3] 增量扫描全部用例: {len(case_ids)} 条")

        if not case_ids:
            print("  无待同步用例，退出")
            return

        # 2. 增量同步（index_single 内部按 index_hash 跳过未变更）
        print("[2/3] 开始增量同步（未变更自动跳过）...")
        t0 = time.time()
        progress: IndexProgress = await index_batch(db, case_ids)
        elapsed = time.time() - t0

        # 3. 汇总
        print()
        print("=" * 60)
        print(f"  总计: {progress.total}")
        print(f"  已索引: {progress.indexed}")
        print(f"  跳过(未变更): {progress.skipped}")
        print(f"  失败: {progress.failed}")
        print(f"  耗时: {elapsed:.1f}s")
        if progress.errors:
            print(f"  错误详情 (前10条):")
            for err in progress.errors[:10]:
                print(f"    - {err}")
        print("=" * 60)

    if progress.failed == 0:
        print("\n  增量同步完成!")
    else:
        print(f"\n  同步完成，但 {progress.failed} 条失败，请查看上方错误详情")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  已手动中断")
        sys.exit(130)
