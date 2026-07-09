"""历史记录 API — /api/history"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.common import ok
from backend.service.history_service import get_history_items

logger = logging.getLogger("history_api")

router = APIRouter(prefix="/api/history", tags=["历史记录"])


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
