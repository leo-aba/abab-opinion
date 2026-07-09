"""头部统计栏 API — /api/stats/*"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.common import ok
from backend.service.dashboard_service import get_header_stats

logger = logging.getLogger("stats_api")

router = APIRouter(prefix="/api/stats", tags=["统计"])


@router.get("/header", summary="获取顶部统计栏数据")
async def header_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回页面顶部 4 个统计数字，所有页面共享。

    返回:
    - today_comments: int            今日评论数
    - new_videos: int                本月新增视频数
    - analysis_completion_rate: int  分析完成率（百分比整数）
    - hot_topic: str                 近期最热话题名
    """
    data = await get_header_stats(db, current_user.id)
    return ok(data)
