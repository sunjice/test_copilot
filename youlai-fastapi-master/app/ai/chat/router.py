"""AI 对话系统 — Router 路由（/api/v1/aitc/chat/*）。"""

import asyncio
import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.response import Result
from app.auth.schemas import SysUserDetails
from app.ai.chat.usecases import ChatUseCase
from app.ai.config import resolve_ai_config
from app.ai.chat.schemas import (
    SessionCreate, SessionUpdate, SessionVO,
    MessageSendReq, MessageVO,
    ContextSetReq, SkillInfoVO,
    ConfirmCreateTaskReq, UpdateCardStatusReq, CancelConfirmReq,
)
from app.ai.agent.skills.base import skill_registry
from app.ai.chat.session_manager import SessionContext
from app.ai.chat.orchestrator import chat_orchestrator
from app.aitc.task.schemas import TaskCreate
from app.aitc.task.engine import TaskEngine

router = APIRouter(prefix="/api/v1/aitc/chat", tags=["AI对话"])


def _get_owner_id(user: SysUserDetails) -> int | None:
    """获取用于隔离的用户ID：超管返回 None（可见全部），普通用户返回 userId。"""
    if user.isRoot:
        return None
    return user.userId


# ═══════════════ 会话 ═══════════════

@router.post("/sessions")
async def create_session(
    req: SessionCreate,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    usecase = ChatUseCase(db)
    data = await usecase.create_session(req, user_id=user.userId)
    return Result(data=data)


@router.get("/sessions")
async def list_sessions(
    domain: str | None = Query(None, description="域筛选"),
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    usecase = ChatUseCase(db)
    owner_id = _get_owner_id(user)
    data = await usecase.list_sessions(domain=domain, user_id=owner_id)
    return Result(data=data)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    usecase = ChatUseCase(db)
    data = await usecase.get_session(session_id, user_id=_get_owner_id(user))
    return Result(data=data)


@router.put("/sessions/{session_id}")
async def update_session(
    session_id: int,
    req: SessionUpdate,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    usecase = ChatUseCase(db)
    data = await usecase.update_session(session_id, req, user_id=_get_owner_id(user))
    return Result(data=data)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    usecase = ChatUseCase(db)
    await usecase.delete_session(session_id, user_id=_get_owner_id(user))
    return Result(data=None, msg="删除成功")


# ═══════════════ 消息 ═══════════════

async def _stream_with_heartbeat(
    stream: AsyncGenerator[str, None],
    heartbeat_interval: float = 25.0,
) -> AsyncGenerator[str, None]:
    """消费异步生成器并返回 SSE 事件；长时间无输出时发送 heartbeat 注释。

    注意：不要直接对同一个 async generator 反复调用 __anext__() 并 cancel，
    否则会触发 `anext(): asynchronous generator is already running`。
    这里使用独立的 consumer task + Queue 解耦心跳与生成器消费。
    """
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

    async def _consumer() -> None:
        try:
            async for sse in stream:
                await queue.put(("event", sse))
            await queue.put(("done", None))
        except Exception as exc:
            await queue.put(("error", exc))

    consumer = asyncio.create_task(_consumer())
    try:
        while True:
            try:
                kind, payload = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
                continue

            if kind == "done":
                break
            if kind == "error":
                raise payload
            yield payload
            queue.task_done()
    finally:
        consumer.cancel()
        try:
            await consumer
        except asyncio.CancelledError:
            pass


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    usecase = ChatUseCase(db)
    data = await usecase.get_messages(session_id, user_id=_get_owner_id(user))
    return Result(data=data)


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    req: MessageSendReq,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """发送消息 — SSE 流式响应（不经过统一 Result 封装，直接返回 SSE 流）。"""
    usecase = ChatUseCase(db)
    owner_id = _get_owner_id(user)

    async def event_stream() -> AsyncGenerator[str, None]:
        async for sse in _stream_with_heartbeat(
            usecase.send_message_stream(session_id, req, owner_id),
            heartbeat_interval=25,
        ):
            yield sse

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════ 确认卡片 ═══════════════

@router.post("/sessions/{session_id}/cancel-confirm")
async def cancel_confirm(
    session_id: int,
    req: CancelConfirmReq | None = None,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """用户取消 confirm_card 创建任务，回写消息状态（多卡片时可指定 card_seq）。"""
    usecase = ChatUseCase(db)
    # 校验会话所有权
    await usecase.get_session(session_id, user_id=_get_owner_id(user))
    card_seq = req.card_seq if req else None
    await usecase.update_card_metadata_by_seq(
        session_id,
        "confirm_card",
        card_seq,
        {"state": "cancelled"},
    )
    return Result(data=None, msg="已取消")


@router.post("/sessions/{session_id}/update-card-status")
async def update_card_status(
    session_id: int,
    req: UpdateCardStatusReq,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """通用卡片状态更新：更新会话中最后一条指定类型卡片的 metadata。"""
    usecase = ChatUseCase(db)
    # 校验会话所有权
    await usecase.get_session(session_id, user_id=_get_owner_id(user))
    await usecase.update_last_card_metadata_by_type(session_id, req.msg_type, req.metadata)
    return Result(data=None, msg="卡片状态已更新")


# ═══════════════ 上下文 ═══════════════

@router.post("/context")
async def set_context(
    session_id: int,
    req: ContextSetReq,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """页面切换时更新会话上下文。"""
    usecase = ChatUseCase(db)
    await usecase.set_context(session_id, req, user_id=_get_owner_id(user))
    return Result(data=None, msg="上下文已更新")


# ═══════════════ 技能 ═══════════════

@router.get("/skills")
async def list_skills(
    domain: str | None = Query(None, description="域筛选，不传则返回全部"),
):
    """获取可用技能列表。"""
    skills = (
        skill_registry.list_by_domain(domain)
        if domain
        else skill_registry.list_all()
    )
    data = [
        SkillInfoVO(
            name=s.name,
            domain=s.domain,
            description=s.description,
            mode=s.mode.value,
            keywords=s.keywords,
        )
        for s in skills
    ]
    return Result(data=data)


# ═══════════════ 任务确认 ═══════════════

@router.post("/sessions/{session_id}/confirm-create-task")
async def confirm_create_task(
    session_id: int,
    req: ConfirmCreateTaskReq,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """用户在对话框中确认创建任务。"""
    usecase = ChatUseCase(db)

    # 创建任务
    engine = TaskEngine(db)
    task_vo = await engine.create_task(
        TaskCreate(
            task_type=req.skill_name,
            project_id=req.project_id,
            suite_id=req.suite_id,
            case_ids=req.case_ids,
            session_id=session_id,
        ),
        create_by=user.username,
    )

    # 回写卡片 part，标记已确认并内嵌任务信息
    # （任务进度直接展示在确认卡片中，不再单独写 task_card 消息）
    confirm_meta: dict = {
        "state": "confirmed",
        "task_id": task_vo.id,
        "task_status": 0,
        "done_count": 0,
        "total_count": task_vo.total_count,
    }
    if req.selected_option:
        confirm_meta["selected_option"] = req.selected_option
    await usecase.update_card_metadata_by_seq(
        session_id,
        "confirm_card",
        req.card_seq,
        confirm_meta,
    )

    return Result(data={
        "task_id": task_vo.id,
        "total_count": task_vo.total_count,
    })
