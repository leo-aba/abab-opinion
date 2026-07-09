"""Dashboard API — /api/dashboard/*"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.common import ok
from backend.service.dashboard_service import get_dashboard_summary

logger = logging.getLogger("dashboard_api")

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/summary", summary="获取仪表盘摘要数据")
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回 Dashboard 页面的 4 个统计卡片数据。

    包含：评论总数、视频数量、热门 Topic、平均情绪，以及较上月的环比变化。

    返回字段:
    - total_comments: int            评论总数（当月）
    - total_comments_change: float   评论数环比变化百分比
    - total_comments_change_direction: "up" | "down"
    - total_videos: int              视频总数（全部时间）
    - total_videos_change: float     视频数环比变化百分比
    - total_videos_change_direction: "up" | "down"
    - hot_topic_name: string         热门话题名称
    - hot_topic_comment_count: int   热门话题关联评论数
    - avg_sentiment: string          平均情绪（正面/负面/中性）
    - avg_sentiment_change: float    正面率环比变化（百分点）
    - avg_sentiment_change_direction: "up" | "down"

    所有数据按当前登录用户隔离。
    """
    data = await get_dashboard_summary(db, current_user.id)
    return ok(data)
