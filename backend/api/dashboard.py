"""Dashboard API — /api/dashboard/*"""

import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.common import ok
from backend.service.dashboard_service import (
    get_dashboard_summary,
    get_dashboard_trend,
    get_dashboard_sentiment_ratio,
    get_dashboard_top_topics,
    get_dashboard_active_tracking,
)

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


@router.get("/trend", summary="获取评论增长趋势")
async def dashboard_trend(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回近 N 天每天的评论数量，用于折线图。

    返回:
    - labels: [str]  日期标注（MM-DD 格式）
    - values: [int]  当日评论数（含零值日）
    """
    data = await get_dashboard_trend(db, current_user.id, days=days)
    return ok(data)


@router.get("/sentiment-ratio", summary="获取情绪占比")
async def dashboard_sentiment_ratio(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回用户所有评论的正/负/中性分布，用于环形图。

    返回:
    - positive: int
    - negative: int
    - neutral: int
    """
    data = await get_dashboard_sentiment_ratio(db, current_user.id)
    return ok(data)


@router.get("/top-topics", summary="获取 TOP N 热门话题")
async def dashboard_top_topics(
    limit: int = Query(10, ge=1, le=50, description="返回条数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回用户范围内评论数最多的 TOP N 话题，用于柱状图。

    返回:
    - [{topic_name: str, comment_count: int}]
    """
    data = await get_dashboard_top_topics(db, current_user.id, limit=limit)
    return ok(data)


@router.get("/active-tracking", summary="获取活跃追踪任务")
async def dashboard_active_tracking(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回当前用户最近的已完成追踪任务列表，用于动态卡片区。

    返回:
    - [{task_id, video_title, platform, author,
        new_comments, credits_remaining, duration_seconds}]
    """
    data = await get_dashboard_active_tracking(db, current_user.id)
    return ok(data)
