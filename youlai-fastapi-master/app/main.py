"""主入口 — FastAPI 应用工厂，挂载路由、中间件、异常处理器。"""

from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi_pagination import add_pagination
from loguru import logger
from app.config import settings
from app.redis import close_redis
from app.middleware import setup_cors, RequestLogMiddleware, IpRateLimitMiddleware
from app.exceptions import (
    BusinessException,
    business_exception_handler,
    global_exception_handler,
    validation_exception_handler,
)
import app.registry  # noqa: F401  注册全部域模型，供 mapper 配置时解析跨域 relationship


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动初始化、关闭释放资源。"""
    logger.info(f"test-copilot starting | session_type={settings.SESSION_TYPE}")

    # 启动 AI 任务调度器（DB 轮询 + Redis 分布式锁）
    from app.ai.agent.tasks.scheduler import get_scheduler
    scheduler = get_scheduler()
    await scheduler.start()

    # 启动 TaskWorker（消费队列并执行任务）
    from app.ai.agent.tasks.worker import get_worker
    worker = get_worker()
    await worker.start()

    # 启动 AI 用量每日汇总（每天凌晨 2:30 聚合昨天用量）
    from app.ai.llm_log.aggregator import get_usage_aggregator
    aggregator = get_usage_aggregator()
    await aggregator.start()

    # 启动 AI 运行事件定时清理（每天凌晨 3:00 删除过期事件）
    from app.ai.llm_log.cleanup import get_llm_log_cleanup
    cleanup = get_llm_log_cleanup()
    await cleanup.start()

    # 预热 LLM 客户端（httpx 连接池），避免首请求卡 2 秒
    from app.ai.agent.graph.builder import prewarm_llm
    await prewarm_llm()

    yield

    await aggregator.stop()
    await cleanup.stop()
    await scheduler.stop()
    await worker.stop()
    await close_redis()
    logger.info("test-copilot shutdown complete")


def create_app() -> FastAPI:
    """构建 FastAPI 实例，注册路由、中间件与异常处理器。"""
    app = FastAPI(
        title="test-copilot",
        description="test-copilot AI 测试助手平台后端",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── 中间件（栈式，后添加的在外层）──
    setup_cors(app)
    app.add_middleware(RequestLogMiddleware)

    # ── 限流（IP 滑动窗口 ZSet Lua）──
    app.add_middleware(IpRateLimitMiddleware)

    # ── 异常处理 ──
    app.add_exception_handler(BusinessException, business_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # ── fastapi-pagination ──
    add_pagination(app)

    # ── 健康检查端点 ──
    @app.get("/health", tags=["系统"], summary="健康检查")
    async def health_check():
        return {"status": "ok", "service": "test-copilot"}

    # ── 注册路由 ──
    from app.auth.router import router as auth_router
    from app.auth.qr_code import router as qr_code_router
    from app.system.user.router import router as user_router
    from app.system.role.router import router as role_router
    from app.system.menu.router import router as menu_router
    from app.system.dept.router import router as dept_router
    from app.system.dict.router import router as dict_router
    from app.system.config.router import router as config_router
    from app.system.notice.router import router as notice_router
    from app.system.log.router import router as log_router
    from app.aitc.router import router as aitc_router
    from app.ai.chat.router import router as chat_router
    from app.ai.llm_log.router import router as llm_log_router
    from app.tool.file.router import router as file_router
    from app.tool.wxma.router import router as wxma_router

    app.include_router(auth_router)
    app.include_router(qr_code_router)
    app.include_router(user_router)
    app.include_router(role_router)
    app.include_router(menu_router)
    app.include_router(dept_router)
    app.include_router(dict_router)
    app.include_router(config_router)
    app.include_router(notice_router)
    app.include_router(log_router)
    app.include_router(aitc_router, prefix="/api/v1/aitc")
    app.include_router(chat_router)
    app.include_router(llm_log_router)
    app.include_router(file_router)
    app.include_router(wxma_router)

    # ── SSE 端点 ──
    from app.tool.sse.router import router as sse_router
    app.include_router(sse_router)

    logger.info("All routers registered")
    return app


app = create_app()
