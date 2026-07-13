"""分析结果 API — /api/results/*"""

import logging
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.models.analysis_task import AnalysisTask
from backend.schemas.common import ok
from datetime import datetime as dt_datetime

from backend.service.results_service import (
    get_overview,
    get_sentiment_ratio,
    get_topics_list,
    get_topic_detail,
    get_ai_summary,
    search_comments,
    get_trend,
    get_trends_detail,
    get_sentiment_attribute,
)
from backend.service.tracking_service import get_tracking_status as _get_ts
from backend.service.report_service import (
    build_report_data,
    send_report_email,
    check_rate_limit,
    mark_rate_limit,
)

logger = logging.getLogger("results_api")

router = APIRouter(prefix="/api/results", tags=["分析结果"])


# ── 通用校验 ──


async def _get_task(task_id: str, user: User, db: AsyncSession) -> AnalysisTask:
    """校验任务存在且属于当前用户。"""
    task = await db.get(AnalysisTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    return task


# ──────────────────────────────────────────────
# 概览
# ──────────────────────────────────────────────


@router.get("/{task_id}/overview", summary="分析概览")
async def overview(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回分析概览数据：视频标题、评论数、话题数、情感占比。"""
    await _get_task(task_id, current_user, db)
    try:
        data = await get_overview(db, task_id)
        return ok(data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ──────────────────────────────────────────────
# 情感比例
# ──────────────────────────────────────────────


@router.get("/{task_id}/sentiment-ratio", summary="情感比例")
async def sentiment_ratio(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回情感分布（positive/negative/neutral 计数）。"""
    await _get_task(task_id, current_user, db)
    data = await get_sentiment_ratio(db, task_id)
    return ok(data)


# ──────────────────────────────────────────────
# 话题列表
# ──────────────────────────────────────────────


@router.get("/{task_id}/topics", summary="话题列表")
async def topics(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回话题列表（名称 + 评论数）。"""
    await _get_task(task_id, current_user, db)
    data = await get_topics_list(db, task_id)
    return ok(data)


# ──────────────────────────────────────────────
# 话题详情
# ──────────────────────────────────────────────


@router.get("/{task_id}/topic/{topic_name:path}/detail", summary="话题详情")
async def topic_detail(
    task_id: str,
    topic_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回单个话题详情：关键词、AI总结、示例评论等。"""
    await _get_task(task_id, current_user, db)
    try:
        decoded_name = unquote(topic_name)
        data = await get_topic_detail(db, task_id, decoded_name)
        return ok(data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ──────────────────────────────────────────────
# AI 总结
# ──────────────────────────────────────────────


@router.get("/{task_id}/ai-summary", summary="AI 总结")
async def ai_summary(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回 AI 生成的综合分析总结。"""
    await _get_task(task_id, current_user, db)
    try:
        data = await get_ai_summary(db, task_id)
        return ok(data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ──────────────────────────────────────────────
# 评论搜索
# ──────────────────────────────────────────────


@router.get("/{task_id}/comments/search", summary="评论搜索")
async def comments_search(
    task_id: str,
    keyword: str = Query("", description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """搜索评论，支持关键词高亮和分页。"""
    await _get_task(task_id, current_user, db)
    data = await search_comments(db, task_id, keyword=keyword, page=page, page_size=page_size)
    return ok(data)


# ──────────────────────────────────────────────
# 属性情感（用话题作为属性维度）
# ──────────────────────────────────────────────


@router.get("/{task_id}/sentiment-attribute", summary="属性情感")
async def sentiment_attribute(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """每个话题作为一个属性维度，展示旭日图和正/负面雷达图。"""
    await _get_task(task_id, current_user, db)
    data = await get_sentiment_attribute(db, task_id)
    return ok(data)


# ──────────────────────────────────────────────
# 时间趋势
# ──────────────────────────────────────────────


@router.get("/{task_id}/trend", summary="评论趋势")
async def trend(
    task_id: str,
    granularity: str = Query("day", description="粒度: day / hour / week"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """概览页评论数量趋势线图。"""
    await _get_task(task_id, current_user, db)
    data = await get_trend(db, task_id, granularity=granularity)
    return ok(data)


@router.get("/{task_id}/trends-detail", summary="趋势详情")
async def trends_detail(
    task_id: str,
    granularity: str = Query("day", description="粒度: day / hour / week"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分情感（正面/负面/总计）的趋势多线图。"""
    await _get_task(task_id, current_user, db)
    data = await get_trends_detail(db, task_id, granularity=granularity)
    return ok(data)


@router.get("/{task_id}/tracking-status", summary="追踪状态")
async def tracking_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询分析任务是否已关联追踪任务及其状态。

    Returns:
        {is_tracking: bool, tracking_id, new_comments, total_comments, credits_remaining,
         new_comments_sentiment, new_comments_topics, analyzed_comments, last_analyzed_at}
    """
    from sqlalchemy import select
    from backend.models.tracking_task import TrackingTask, TrackingStatus

    task = await _get_task(task_id, current_user, db)

    result = await db.execute(
        select(TrackingTask).where(
            TrackingTask.analysis_task_id == task_id,
        ).order_by(TrackingTask.started_at.desc()).limit(1)
    )
    tracking = result.scalar_one_or_none()

    if not tracking:
        return ok({
            "is_tracking": False,
            "tracking_id": None,
            "new_comments": 0,
            "total_comments": task.total_comments_processed or 0,
            "credits_remaining": 0,
            "new_comments_sentiment": {"positive": 0, "negative": 0, "neutral": 0},
            "new_comments_topics": [],
            "analyzed_comments": 0,
            "last_analyzed_at": None,
        })

    try:
        status_data = await _get_ts(tracking.id, db)
    except ValueError:
        status_data = {}

    user = await db.get(User, current_user.id) if hasattr(User, 'credits') else None
    duration_seconds = 0
    if tracking.started_at:
        duration_seconds = int((dt_datetime.utcnow() - tracking.started_at).total_seconds())

    return ok({
        "is_tracking": tracking.status == TrackingStatus.active,
        "tracking_id": tracking.id,
        "new_comments": tracking.new_comments_since_start or 0,
        "total_comments": task.total_comments_processed or 0,
        "credits_remaining": user.credits if user else 0,
        "new_comments_sentiment": status_data.get("new_comments_sentiment", {"positive": 0, "negative": 0, "neutral": 0}),
        "new_comments_topics": status_data.get("new_comments_topics", []),
        "analyzed_comments": status_data.get("analyzed_comments", 0),
        "last_analyzed_at": status_data.get("last_analyzed_at"),
        "duration_seconds": duration_seconds,
    })


# ──────────────────────────────────────────────
# 发送分析报告到邮箱
# ──────────────────────────────────────────────


@router.post("/{task_id}/send-report", summary="发送分析报告到邮箱")
async def send_report(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将当前分析结果的摘要报告发送到用户注册邮箱。

    限制: 同用户同任务 60 秒内只能发送一次。
    """
    task = await _get_task(task_id, current_user, db)

    # 校验任务状态
    if task.status.value != "completed":
        raise HTTPException(status_code=400, detail="分析尚未完成，无法发送报告")

    # 校验用户邮箱
    if not current_user.email:
        raise HTTPException(status_code=400, detail="请先在设置中绑定邮箱")

    # 频率限制
    wait = check_rate_limit(current_user.id, task_id)
    if wait is not None:
        raise HTTPException(status_code=429, detail=f"请 {wait} 秒后再试")

    # 组装报告数据并发送
    try:
        report_data = await build_report_data(db, task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    ok_result = await send_report_email(current_user.email, report_data)
    if not ok_result:
        logger.error("发送报告失败: task_id=%s, user=%s, email=%s",
                      task_id, current_user.username, current_user.email)
        raise HTTPException(status_code=502, detail="邮件发送失败，请稍后重试")

    mark_rate_limit(current_user.id, task_id)
    logger.info("报告已发送: task_id=%s, user=%s, email=%s",
                task_id, current_user.username, current_user.email)
    return ok(None, "报告已发送至您的注册邮箱")
