"""检索域 — 正式业务路由（同义词管理等，供前端页面调用）。

区别于 management/debug.py（调试与运维入口），本模块为可对接前端页面的
正式 CRUD 接口，统一走 Result 响应 + 权限校验。
"""

from fastapi import APIRouter, Depends, Query
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_perm
from app.exceptions import BusinessException
from app.pagination import PageResult
from app.response import Result, ResultCode
from app.aitc.constants import (
    PERM_SYNONYM_LIST, PERM_SYNONYM_CREATE, PERM_SYNONYM_UPDATE,
    PERM_SYNONYM_DELETE, PERM_SYNONYM_SYNC,
)
from app.aitc.retrieval.common.synonyms import SynonymsManager
from app.aitc.retrieval.schemas import SynonymCreate, SynonymItem, SynonymUpdate

router = APIRouter(prefix="/retrieval/synonyms", tags=["检索管理"])


def _to_item(row) -> SynonymItem:
    return SynonymItem(
        id=row.id,
        synonym_group=row.synonym_group,
        term=row.term,
        is_preferred=row.is_preferred,
        domain=row.domain,
        created_at=str(row.created_at) if row.created_at else None,
        updated_at=str(row.updated_at) if row.updated_at else None,
    )


async def _sync_to_es(manager: SynonymsManager, db: AsyncSession) -> str:
    """将 PG 同义词同步到 ES。ES 不可用时降级为提示，不阻断 CRUD。"""
    try:
        count = await manager.sync_to_es(db)
        return f"已同步 {count} 组同义词到 ES" if count else "当前无同义词组可同步"
    except Exception as exc:  # noqa: BLE001 — ES 故障不应阻断词条管理
        logger.warning(f"同义词同步 ES 失败: {exc}")
        return f"数据已保存，但 ES 同步失败: {exc}"


@router.get("", summary="同义词列表", dependencies=[Depends(require_perm(PERM_SYNONYM_LIST))])
async def list_synonyms(
    pageNum: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    domain: str | None = Query(default=None, description="按领域过滤"),
    keyword: str | None = Query(default=None, description="按词条/分组模糊搜索"),
    db: AsyncSession = Depends(get_db),
):
    manager = SynonymsManager()
    total, rows = await manager.list_synonyms(
        db, page_num=pageNum, page_size=pageSize, domain=domain, keyword=keyword
    )
    records = [_to_item(r) for r in rows]
    return Result(data=PageResult(records=records, total=total, pageNum=pageNum, pageSize=pageSize))


@router.post("", summary="新增同义词", dependencies=[Depends(require_perm(PERM_SYNONYM_CREATE))])
async def create_synonym(form: SynonymCreate, db: AsyncSession = Depends(get_db)):
    manager = SynonymsManager()
    if await manager.find_synonym(db, form.synonym_group, form.term):
        raise BusinessException(code=ResultCode.DUPLICATE_KEY, msg="该词条已存在")
    await manager.add_synonym(
        db,
        group=form.synonym_group,
        term=form.term,
        domain=form.domain,
        is_preferred=form.is_preferred,
    )
    tip = await _sync_to_es(manager, db)
    return Result(data=tip, msg="新增成功")


@router.put("/{sid}", summary="更新同义词", dependencies=[Depends(require_perm(PERM_SYNONYM_UPDATE))])
async def update_synonym(sid: int, form: SynonymUpdate, db: AsyncSession = Depends(get_db)):
    manager = SynonymsManager()
    try:
        ok = await manager.update_synonym(
            db,
            sid=sid,
            group=form.synonym_group,
            term=form.term,
            domain=form.domain,
            is_preferred=form.is_preferred,
        )
    except IntegrityError:
        raise BusinessException(code=ResultCode.DUPLICATE_KEY, msg="更新后与现有词条冲突")
    if not ok:
        raise BusinessException(code=ResultCode.DATA_NOT_FOUND, msg="同义词不存在")
    tip = await _sync_to_es(manager, db)
    return Result(data=tip, msg="更新成功")


@router.delete("/{ids}", summary="删除同义词", dependencies=[Depends(require_perm(PERM_SYNONYM_DELETE))])
async def delete_synonyms(ids: str, db: AsyncSession = Depends(get_db)):
    id_list = [int(x) for x in ids.split(",") if x.strip()]
    if not id_list:
        raise BusinessException(code=ResultCode.PARAM_VALID_FAIL, msg="请选择词条")
    manager = SynonymsManager()
    count = await manager.delete_by_ids(db, id_list)
    tip = await _sync_to_es(manager, db)
    return Result(data=count, msg=f"成功删除 {count} 条记录，{tip}")


@router.post("/sync", summary="手动同步同义词到 ES", dependencies=[Depends(require_perm(PERM_SYNONYM_SYNC))])
async def sync_synonyms(db: AsyncSession = Depends(get_db)):
    manager = SynonymsManager()
    tip = await _sync_to_es(manager, db)
    return Result(data=tip, msg="同步完成")
