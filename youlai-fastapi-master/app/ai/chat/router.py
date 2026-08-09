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
from app.ai.chat.service import ChatService
from app.ai.config import resolve_ai_config
from app.ai.chat.schemas import (
    SessionCreate, SessionUpdate, SessionVO,
    MessageSendReq, MessageVO,
    DraftVO, DraftConfirmReq,
    ContextSetReq, SkillInfoVO,
    ConfirmCreateTaskReq, UpdateCardStatusReq,
)
from app.ai.agent.skills.base import skill_registry
from app.ai.chat.session_manager import SessionContext
from app.ai.chat.orchestrator import chat_orchestrator
from app.ai.llm_log.writer import make_trace_id
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
    service = ChatService(db)
    data = await service.create_session(req, user_id=user.userId)
    return Result(data=data)


@router.get("/sessions")
async def list_sessions(
    domain: str | None = Query(None, description="域筛选"),
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    service = ChatService(db)
    owner_id = _get_owner_id(user)
    data = await service.list_sessions(domain=domain, user_id=owner_id)
    return Result(data=data)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    service = ChatService(db)
    data = await service.get_session(session_id, user_id=_get_owner_id(user))
    return Result(data=data)


@router.put("/sessions/{session_id}")
async def update_session(
    session_id: int,
    req: SessionUpdate,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    service = ChatService(db)
    data = await service.update_session(session_id, req, user_id=_get_owner_id(user))
    return Result(data=data)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    service = ChatService(db)
    await service.delete_session(session_id, user_id=_get_owner_id(user))
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
    service = ChatService(db)
    data = await service.get_messages(session_id, user_id=_get_owner_id(user))
    return Result(data=data)


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    req: MessageSendReq,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """发送消息 — SSE 流式响应（不经过统一 Result 封装，直接返回 SSE 流）。"""
    service = ChatService(db)
    owner_id = _get_owner_id(user)

    # 0. 校验会话所有权
    session = await service.get_session(session_id, user_id=owner_id)

    # 1. 保存用户消息
    await service.add_message(session_id, "user", req.content)

    # 2. 获取会话上下文
    history = await service.get_message_history(session_id, limit=30, user_id=owner_id)
    context = SessionContext(
        session_id=session_id,
        domain=session.domain,
        context_json=session.context_json or {},
    )

    # 3. 解析 AI 配置
    ai_config = resolve_ai_config("chat")

    # 4. 注入上下文
    context.working["db_session"] = db
    context.working["ai_config"] = ai_config
    # 生成 trace_id 用于 LLM 调用日志串联
    trace_id = make_trace_id("chat", session_id)
    context.working["trace_id"] = trace_id

    async def event_stream() -> AsyncGenerator[str, None]:
        assistant_content = ""
        assistant_msg_type = "text"
        metadata: dict = {}
        draft_id = None

        try:
            draft_type = None
            draft_data = None

            stream = chat_orchestrator.process_message(
                req.content, context, history
            )
            # 用 heartbeat 包裹：工具执行期间可能 30-60s 无输出，每 25s 发 : heartbeat 防止代理断连
            async for sse in _stream_with_heartbeat(stream, heartbeat_interval=25):
                yield sse

                # 收集 assistant 消息内容 — SSE 是多行字符串(event:xxx\ndata:{...})，需按行解析
                for line in sse.splitlines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:].strip())
                            if isinstance(data, dict):
                                if "content" in data:
                                    assistant_content = data["content"]
                                if "msg_type" in data:
                                    assistant_msg_type = data["msg_type"]
                                if "metadata" in data and data["metadata"]:
                                    metadata = data["metadata"]
                                if "draft_type" in data:
                                    draft_type = data["draft_type"]
                                if "draft_data" in data:
                                    draft_data = data["draft_data"]
                        except (json.JSONDecodeError, KeyError):
                            pass

            # 创建草稿
            if draft_type and draft_data:
                draft = await service.create_draft(
                    session_id=session_id,
                    message_id=0,
                    draft_type=draft_type,
                    title=draft_type,
                    content_json=draft_data,
                )
                draft_id = draft.id

            # 保存 assistant 消息
            if assistant_content:
                await service.add_message(
                    session_id, "assistant",
                    assistant_content,
                    msg_type=assistant_msg_type,
                    metadata=metadata,
                    draft_id=draft_id,
                )

        except Exception as e:
            err_text = f"处理消息时出错: {str(e)}"
            await service.add_message(
                session_id, "assistant", err_text, msg_type="text",
                metadata={"error": str(e)},
            )
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

        # 写入用量日志
        tokens = metadata.get("tokens", {})
        if tokens:
            await service.log_usage(
                module="chat",
                model=ai_config.model if ai_config else "unknown",
                prompt_tokens=tokens.get("prompt", 0),
                completion_tokens=tokens.get("completion", 0),
                duration_ms=metadata.get("duration_ms", 0),
                session_id=session_id,
            )

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════ 草稿 ═══════════════

@router.get("/drafts/{draft_id}")
async def get_draft(
    draft_id: int,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    service = ChatService(db)
    data = await service.get_draft(draft_id, user_id=_get_owner_id(user))
    return Result(data=data)


@router.post("/drafts/{draft_id}/confirm")
async def confirm_draft(
    draft_id: int,
    req: DraftConfirmReq,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """确认草稿：confirm 确认 / discard 丢弃。"""
    service = ChatService(db)
    data = await service.confirm_draft(draft_id, req, user_id=_get_owner_id(user))
    # 回写 draft_card 消息的 metadata_json
    await service.update_message_metadata_by_draft_id(draft_id, {"draft_status": req.action})
    return Result(data=data)


# ═══════════════ 确认卡片 ═══════════════

@router.post("/sessions/{session_id}/cancel-confirm")
async def cancel_confirm(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """用户取消 confirm_card 创建任务，回写消息状态。"""
    service = ChatService(db)
    # 校验会话所有权
    await service.get_session(session_id, user_id=_get_owner_id(user))
    await service.update_last_confirm_card_metadata(session_id, {"confirm_status": "cancelled"})
    return Result(data=None, msg="已取消")


@router.post("/sessions/{session_id}/update-card-status")
async def update_card_status(
    session_id: int,
    req: UpdateCardStatusReq,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """通用卡片状态更新：更新会话中最后一条指定类型卡片的 metadata。"""
    service = ChatService(db)
    # 校验会话所有权
    await service.get_session(session_id, user_id=_get_owner_id(user))
    await service.update_last_card_metadata_by_type(session_id, req.msg_type, req.metadata)
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
    service = ChatService(db)
    await service.set_context(session_id, req, user_id=_get_owner_id(user))
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
    service = ChatService(db)

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

    # 保存 assistant 确认消息
    task_type_label = {"core_select": "挑选核心用例", "case_review": "用例审核", "script_gen": "生成测试脚本", "case_complete": "补全用例字段"}.get(req.skill_name, req.skill_name)
    total_count = task_vo.total_count
    scope_desc = f"已选中的 {total_count} 条" if req.case_ids else "当前模块下的"
    content = f"已创建{task_type_label}任务，将对{scope_desc}用例逐条处理。完成后可点击查看。"

    await service.add_message(
        session_id, "assistant",
        content,
        msg_type="task_card",
        metadata={
            "skill_name": req.skill_name,
            "task_id": task_vo.id,
            "project_id": req.project_id,
            "suite_id": req.suite_id,
            "total": task_vo.total_count,
        },
    )

    # 回写 confirm_card 消息的 metadata_json，标记已确认
    confirm_meta: dict = {"confirm_status": "confirmed"}
    if req.selected_option:
        confirm_meta["_selected_option"] = req.selected_option
    await service.update_last_confirm_card_metadata(session_id, confirm_meta)

    return Result(data={
        "task_id": task_vo.id,
        "total_count": task_vo.total_count,
    })
