"""任务域 — API 路由（/api/v1/aitc/tasks/*）。"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_perm, get_current_user
from app.response import Result
from app.auth.schemas import SysUserDetails
from app.aitc.task.schemas import (
    TaskCreate, TaskQuery, TaskConfirmReq, ReviewItemReq,
)
from app.aitc.task.engine import TaskEngine
from app.aitc.constants import (
    PERM_TASK_CREATE, PERM_TASK_LIST, PERM_TASK_CONFIRM, PERM_TASK_STOP,
)

router = APIRouter(tags=["AI任务"])


# ═══════════════ AI 任务 ═══════════════

@router.post("/tasks", summary="创建AI任务", dependencies=[Depends(require_perm(PERM_TASK_CREATE))])
async def create_task(
    form: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """创建 AI 任务并启动后台执行。"""
    engine = TaskEngine(db)
    result = await engine.create_task(form, create_by=user.username)
    return Result(data=result, msg="任务已创建，已加入排队队列")


@router.get("/tasks", summary="任务分页列表", dependencies=[Depends(require_perm(PERM_TASK_LIST))])
async def get_task_page(
    pageNum: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    projectId: int | None = Query(default=None),
    taskType: str | None = Query(default=None),
    status: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    query = TaskQuery(pageNum=pageNum, pageSize=pageSize, projectId=projectId, taskType=taskType, status=status)
    engine = TaskEngine(db)
    return Result(data=await engine.get_task_page(query))


@router.get("/tasks/{task_id}", summary="任务详情（含明细）", dependencies=[Depends(require_perm(PERM_TASK_LIST))])
async def get_task_detail(task_id: int, db: AsyncSession = Depends(get_db)):
    engine = TaskEngine(db)
    return Result(data=await engine.get_task_detail(task_id))


@router.get("/tasks/{task_id}/items", summary="任务明细列表", dependencies=[Depends(require_perm(PERM_TASK_LIST))])
async def get_task_items(task_id: int, db: AsyncSession = Depends(get_db)):
    engine = TaskEngine(db)
    return Result(data=await engine.get_task_items(task_id))


@router.post("/tasks/{task_id}/rerun", summary="重新执行任务", dependencies=[Depends(require_perm(PERM_TASK_CREATE))])
async def rerun_task(task_id: int, db: AsyncSession = Depends(get_db)):
    engine = TaskEngine(db)
    await engine.rerun_task(task_id)
    return Result(msg="任务已重新加入排队队列")


@router.post("/tasks/{task_id}/confirm", summary="确认任务结果", dependencies=[Depends(require_perm(PERM_TASK_CONFIRM))])
async def confirm_task_items(
    task_id: int,
    form: TaskConfirmReq,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
    request: Request = None,
):
    engine = TaskEngine(db)
    reviewer_ip = request.client.host if request and request.client else ""
    await engine.confirm_task_items(task_id, form, reviewed_by=user.username, reviewer_ip=reviewer_ip)
    return Result(msg="确认成功，结果已应用")


@router.post("/tasks/{task_id}/stop", summary="停止任务", dependencies=[Depends(require_perm(PERM_TASK_STOP))])
async def stop_task(task_id: int, db: AsyncSession = Depends(get_db)):
    engine = TaskEngine(db)
    await engine.stop_task(task_id)
    return Result(msg="任务已停止")


@router.get("/tasks/{task_id}/items/{item_id}", summary="获取单条任务明细+用例详情", dependencies=[Depends(require_perm(PERM_TASK_LIST))])
async def get_task_item_with_case(
    task_id: int, item_id: int, db: AsyncSession = Depends(get_db),
):
    engine = TaskEngine(db)
    return Result(data=await engine.get_item_with_case(task_id, item_id))


@router.post("/tasks/{task_id}/items/{item_id}/review", summary="审核单条明细（含逐字段审核记录）", dependencies=[Depends(require_perm(PERM_TASK_CONFIRM))])
async def review_task_item(
    task_id: int,
    item_id: int,
    form: ReviewItemReq,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
    request: Request = None,
):
    engine = TaskEngine(db)
    reviewer_ip = request.client.host if request and request.client else ""
    await engine.review_single_item(task_id, item_id, form, reviewed_by=user.username, reviewer_ip=reviewer_ip)
    return Result(msg="审核成功")


@router.get("/tasks/{task_id}/review-records", summary="查询任务审核记录", dependencies=[Depends(require_perm(PERM_TASK_LIST))])
async def get_review_records(task_id: int, db: AsyncSession = Depends(get_db)):
    engine = TaskEngine(db)
    return Result(data=await engine.get_review_records(task_id))
