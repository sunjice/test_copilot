"""TestLink 集成 — API 路由（/api/v1/aitc/testlink/*）。

提供手动触发同步/反写/巡检的接口，便于开发联调与运维操作。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.response import Result
from app.auth.schemas import SysUserDetails
from app.aitc.testlink import get_client
from app.aitc.testlink.models import PushRequest, SyncRequest
from app.aitc.testlink.sync_service import TestLinkSyncService
from app.aitc.testlink.push_service import TestLinkPushService

router = APIRouter(tags=["TestLink集成"])


@router.post("/testlink/sync", summary="全量同步（拉取 TestLink 到本地）")
async def sync_project(
    form: SyncRequest,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """手动触发指定项目的全量同步。"""
    client = get_client()
    svc = TestLinkSyncService(client, db)
    stats = await svc.sync_project(form.project_id)
    return Result(data=stats, msg="同步完成")


@router.post("/testlink/push", summary="反写（推送本地到 TestLink）")
async def push_cases(
    form: PushRequest,
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """手动触发反写：指定用例或所有待反写用例。"""
    client = get_client()
    svc = TestLinkPushService(client, db)
    if form.case_ids:
        result = {"pushed": 0, "failed": 0, "errors": []}
        for cid in form.case_ids:
            try:
                ok = await svc.push_case(cid)
                result["pushed" if ok else "failed"] += 1
            except Exception as e:  # noqa: BLE001
                result["failed"] += 1
                result["errors"].append(f"用例 {cid}: {e}")
        return Result(data=result, msg="反写完成")
    result = await svc.push_pending_cases(form.project_id)
    return Result(data=result, msg="反写完成")


@router.post("/testlink/monitor", summary="立即执行一次增量巡检")
async def run_monitor(
    db: AsyncSession = Depends(get_db),
    user: SysUserDetails = Depends(get_current_user),
):
    """手动触发一次增量巡检（等价于每日定时任务单次执行）。"""
    from app.aitc.testlink.monitor import get_testlink_monitor

    stats = await get_testlink_monitor().run_once()
    return Result(data=stats, msg="巡检完成")
