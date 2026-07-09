"""Dashboard 服务层 — 聚合仪表盘所需的统计数据"""

import logging
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.analysis_task import AnalysisTask
from backend.models.comment import Comment
from backend.models.topic import Topic

logger = logging.getLogger("dashboard_service")


async def get_dashboard_summary(db: AsyncSession, user_id: str) -> dict:
    """获取当前用户的 Dashboard 摘要数据。

    数据范围：通过 AnalysisTask.video_id → Comment.video_id 限定当前用户。
    环比时间窗口为"当月 vs 上月"。
    """
    now = datetime.utcnow()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 上月第一天
    if current_month_start.month == 1:
        prev_month_start = current_month_start.replace(
            year=current_month_start.year - 1, month=12
        )
    else:
        prev_month_start = current_month_start.replace(
            month=current_month_start.month - 1
        )

    # ----- 用户所有任务关联的视频 ID（去重） -----
    video_id_rows = await db.execute(
        select(func.distinct(AnalysisTask.video_id)).where(
            AnalysisTask.user_id == user_id
        )
    )
    user_video_ids = [row[0] for row in video_id_rows.all()]

    # ----- 用户无私有机频时的默认返回 -----
    if not user_video_ids:
        return _empty_result()

    # ----- 用户所有任务 ID（用于按 task 限定的查询，如 topic） -----
    task_id_rows = await db.execute(
        select(AnalysisTask.id).where(AnalysisTask.user_id == user_id)
    )
    task_ids = [row[0] for row in task_id_rows.all()]

    # ===== 1. 评论总数（当月，按用户视频限定） =====
    total_comments = await _count_comments_in_range(
        db, user_video_ids, current_month_start, None
    )

    # ===== 2. 评论数环比变化（上月） =====
    prev_comments = await _count_comments_in_range(
        db, user_video_ids, prev_month_start, current_month_start
    )
    total_comments_change, total_comments_change_direction = _calc_change(
        total_comments, prev_comments
    )

    # ===== 3. 视频总数（全部时间） =====
    total_videos = len(user_video_ids)

    # ===== 4. 视频数环比变化 =====
    videos_this_month = await _count_distinct_videos_in_range(
        db, user_id, current_month_start, None
    )
    videos_prev_month = await _count_distinct_videos_in_range(
        db, user_id, prev_month_start, current_month_start
    )
    total_videos_change, total_videos_change_direction = _calc_change(
        videos_this_month, videos_prev_month
    )

    # ===== 5. 热门 Topic（用户范围内评论数最多的 topic） =====
    hot_topic_name, hot_topic_comment_count = await _get_hot_topic(db, task_ids)

    # ===== 6. 平均情绪（众数） =====
    avg_sentiment = await _get_dominant_sentiment(db, user_video_ids)

    # ===== 7. 情绪环比变化 =====
    (
        avg_sentiment_change,
        avg_sentiment_change_direction,
    ) = await _calc_sentiment_change(
        db, user_video_ids, current_month_start, prev_month_start
    )

    return {
        "total_comments": total_comments,
        "total_comments_change": total_comments_change,
        "total_comments_change_direction": total_comments_change_direction,
        "total_videos": total_videos,
        "total_videos_change": total_videos_change,
        "total_videos_change_direction": total_videos_change_direction,
        "hot_topic_name": hot_topic_name,
        "hot_topic_comment_count": hot_topic_comment_count,
        "avg_sentiment": avg_sentiment,
        "avg_sentiment_change": avg_sentiment_change,
        "avg_sentiment_change_direction": avg_sentiment_change_direction,
    }


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _empty_result() -> dict:
    """用户无任何数据时的默认返回"""
    return {
        "total_comments": 0,
        "total_comments_change": 0.0,
        "total_comments_change_direction": "up",
        "total_videos": 0,
        "total_videos_change": 0.0,
        "total_videos_change_direction": "up",
        "hot_topic_name": "暂无",
        "hot_topic_comment_count": 0,
        "avg_sentiment": "中性",
        "avg_sentiment_change": 0.0,
        "avg_sentiment_change_direction": "up",
    }


async def _count_comments_in_range(
    db: AsyncSession,
    video_ids: list[str],
    start: datetime,
    end: datetime | None,
) -> int:
    """统计指定时间范围内、指定视频的评论数。end=None 表示到现在。"""
    conditions = [Comment.video_id.in_(video_ids), Comment.create_time >= start]
    if end is not None:
        conditions.append(Comment.create_time < end)

    result = await db.execute(
        select(func.count(Comment.id)).where(*conditions)
    )
    return result.scalar() or 0


async def _count_distinct_videos_in_range(
    db: AsyncSession,
    user_id: str,
    start: datetime,
    end: datetime | None,
) -> int:
    """统计指定时间范围内新增的独立视频数（通过分析任务创建时间）。"""
    conditions = [
        AnalysisTask.user_id == user_id,
        AnalysisTask.created_at >= start,
    ]
    if end is not None:
        conditions.append(AnalysisTask.created_at < end)

    result = await db.execute(
        select(func.count(func.distinct(AnalysisTask.video_id))).where(*conditions)
    )
    return result.scalar() or 0


def _calc_change(current: int, previous: int) -> tuple[float, str]:
    """计算环比百分比变化，返回 (change_pct, direction)"""
    if previous > 0:
        change = round((current - previous) / previous * 100, 1)
    elif current > 0:
        change = 100.0
    else:
        change = 0.0
    direction = "up" if change >= 0 else "down"
    return change, direction


async def _get_hot_topic(
    db: AsyncSession, task_ids: list[str]
) -> tuple[str, int]:
    """获取用户范围内评论数最多的 Topic 名称和评论数。

    通过 Topic.task_id 限定用户范围（topics 表有 task_id 列）。
    """
    result = await db.execute(
        select(Topic.name, func.count(Comment.id).label("cnt"))
        .join(Comment, Comment.topic_id == Topic.id)
        .where(Topic.task_id.in_(task_ids))
        .group_by(Topic.id, Topic.name)
        .order_by(func.count(Comment.id).desc())
        .limit(1)
    )
    row = result.one_or_none()
    if row is not None and row.cnt > 0:
        return row.name, row.cnt
    return "暂无", 0


_SENTIMENT_MAP = {"positive": "正面", "negative": "负面", "neutral": "中性"}


async def _get_dominant_sentiment(
    db: AsyncSession, video_ids: list[str]
) -> str:
    """获取用户所有评论中出现最多的情感倾向（众数），映射为中文标签。

    如果所有评论的 sentiment 均为 NULL 或用户无评论，默认返回"中性"。
    """
    result = await db.execute(
        select(
            Comment.sentiment,
            func.count(Comment.id).label("cnt"),
        )
        .where(
            Comment.video_id.in_(video_ids),
            Comment.sentiment.isnot(None),
        )
        .group_by(Comment.sentiment)
    )
    rows = result.all()
    if not rows:
        return "中性"

    # 找出现次数最多的 sentiment
    best_sentiment = max(rows, key=lambda r: r.cnt).sentiment
    return _SENTIMENT_MAP.get(best_sentiment, "中性")


async def _calc_sentiment_change(
    db: AsyncSession,
    video_ids: list[str],
    current_month_start: datetime,
    prev_month_start: datetime,
) -> tuple[float, str]:
    """计算当月 vs 上月的正面评论占比变化（百分点差值）。"""
    # 当月
    this_positive, this_total = await _count_sentiment_in_range(
        db, video_ids, current_month_start, None
    )
    # 上月
    prev_positive, prev_total = await _count_sentiment_in_range(
        db, video_ids, prev_month_start, current_month_start
    )

    this_pct = (this_positive / this_total * 100) if this_total > 0 else 0.0
    prev_pct = (prev_positive / prev_total * 100) if prev_total > 0 else 0.0

    change = round(this_pct - prev_pct, 1)
    direction = "up" if change >= 0 else "down"
    return change, direction


async def _count_sentiment_in_range(
    db: AsyncSession,
    video_ids: list[str],
    start: datetime,
    end: datetime | None,
) -> tuple[int, int]:
    """统计指定时间范围内的 (正面评论数, 总评论数)。

    只计算 sentiment 不为 NULL 的评论。
    """
    common_conds = [
        Comment.video_id.in_(video_ids),
        Comment.create_time >= start,
        Comment.sentiment.isnot(None),
    ]
    if end is not None:
        common_conds.append(Comment.create_time < end)

    positive_conds = [*common_conds, Comment.sentiment == "positive"]

    total_result = await db.execute(
        select(func.count(Comment.id)).where(*common_conds)
    )
    positive_result = await db.execute(
        select(func.count(Comment.id)).where(*positive_conds)
    )

    return (positive_result.scalar() or 0, total_result.scalar() or 0)
