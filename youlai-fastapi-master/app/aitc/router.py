"""测试部 AI 助手 — 聚合路由。
各域路由分别定义在 case/sample/script/spec/task 子包中。本文件聚合所有子路由。
所有 URL 保持不变（/api/v1/aitc/...），前缀由 main.py 统一注入。
"""

from fastapi import APIRouter

from app.aitc.case.router import router as case_router
from app.aitc.sample.router import router as sample_router
from app.aitc.script.router import router as script_router
from app.aitc.spec.router import router as spec_router
from app.aitc.task.router import router as task_router
from app.aitc.testlink.router import router as testlink_router
from app.aitc.retrieval.management.debug import router as retrieval_debug_router
from app.aitc.retrieval.router import router as retrieval_router

router = APIRouter(tags=["测试部AI助手"])

router.include_router(case_router)
router.include_router(sample_router)
router.include_router(script_router)
router.include_router(spec_router)
router.include_router(task_router)
router.include_router(testlink_router)
router.include_router(retrieval_debug_router)
router.include_router(retrieval_router)
