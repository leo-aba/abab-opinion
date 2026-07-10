"""追踪任务 API — /api/tracking/*"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.models.tracking_task import TrackingTask
from backend.schemas.common import ok
from backend.service.tracking_service import (
    get_tracking_status,
    stop_tracking,
    get_user_active_tracking_tasks,
    has_active_tracking,
)
logger = logging.getLogger("tracking_api")

router = APIRouter(prefix="/api/tracking", tags=["追踪任务"])


@router.get("/{tracking_id}/status", summary="查询追踪实时状态")
async def tracking_status(
    tracking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询追踪任务的实时状态，供前端 pipeline 页轮询（每 5 秒）。

    Returns:
        {active, new_comments, credits_remaining, credits_total, total_comments, total_topics}
    """
    try:
        tracking = await db.get(TrackingTask, tracking_id)
        if not tracking:
            raise HTTPException(status_code=404, detail="追踪任务不存在")
        if tracking.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        status_data = await get_tracking_status(tracking_id, db)
        return ok(status_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{tracking_id}/stop", summary="停止追踪任务")
async def tracking_stop(
    tracking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动停止追踪任务。

    Returns:
        {stopped_at, total_new_comments, credits_consumed}
    """
    tracking = await db.get(TrackingTask, tracking_id)
    if not tracking:
        raise HTTPException(status_code=404, detail="追踪任务不存在")
    if tracking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")

    result = await stop_tracking(tracking_id, db)
    return ok(result)


@router.get("/tasks", summary="获取所有追踪任务列表")
async def list_tracking_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的所有追踪任务列表，供追踪页面使用。

    Returns:
        [{tracking_id, task_id, video_title, platform, author,
          status, new_comments, credits_consumed, total_comments,
          credits_remaining, duration_seconds, analysis_finished_at, recent_logs}]
    """
    items = await get_user_active_tracking_tasks(db, current_user.id)
    # 补充 credits_remaining（同用户所有追踪任务共享）
    user_credits = current_user.credits
    for item in items:
        item["credits_remaining"] = user_credits

    return ok(items)


@router.get("/has-active", summary="检查是否有活跃追踪")
async def check_has_active(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检查当前用户是否有活跃的追踪任务。

    Returns:
        {has_active: bool}
    """
    active = await has_active_tracking(db, current_user.id)
    return ok({"has_active": active})
