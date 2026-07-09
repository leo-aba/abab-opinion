"""历史记录 API — /api/history"""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.common import ok
from backend.service.history_service import get_history_items, delete_history_task, batch_delete_history

logger = logging.getLogger("history_api")

router = APIRouter(prefix="/api/history", tags=["历史记录"])


class BatchDeleteRequest(BaseModel):
    """批量删除请求体"""
    task_ids: list[str]


@router.get("", summary="获取历史分析记录列表")
async def history_list(
    platform: str | None = Query(None, description="平台过滤: bilibili | douyin"),
    time_range: str | None = Query(
        None, alias="time_range", description="时间范围: 7d | 30d | 3m"
    ),
    keyword: str | None = Query(None, description="搜索视频标题关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    sort_by: str | None = Query(
        None,
        description="排序字段: video_title | topic_count | comment_count | analyzed_at",
    ),
    sort_order: str = Query("desc", description="排序方向: asc | desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询当前用户的历史分析记录，支持筛选、排序和分页。

    返回字段:
    - total / total_pages / page / page_size: 分页信息
    - items: 列表项，每项包含 task_id / video_title / platform /
             analysis_mode / topic_count / comment_count / analyzed_at /
             status / status_label
    """
    data = await get_history_items(
        db,
        current_user.id,
        platform=platform,
        time_range=time_range,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return ok(data)


@router.delete("/{task_id}", summary="删除单条历史记录")
async def history_delete(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除指定的历史分析记录（含关联的评论和话题数据）。"""
    ok_delete = await delete_history_task(db, task_id, current_user.id)
    if not ok_delete:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="记录不存在、无权删除或任务仍在进行中",
        )
    logger.info("用户 %s 删除了历史记录 %s", current_user.username, task_id)
    return ok({"task_id": task_id})


@router.post("/batch-delete", summary="批量删除历史记录")
async def history_batch_delete(
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量删除历史分析记录。"""
    if not body.task_ids:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="task_ids 不能为空")

    result = await batch_delete_history(db, body.task_ids, current_user.id)
    logger.info(
        "用户 %s 批量删除了 %d 条历史记录",
        current_user.username, result["deleted_count"],
    )
    return ok(result)
