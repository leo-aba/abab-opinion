"""Dashboard 服务层 — 聚合仪表盘所需的统计数据"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.analysis_task import AnalysisTask, AnalysisStatus
from backend.models.comment import Comment
from backend.models.topic import Topic
from backend.models.video import Video

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
    """统计指定时间范围内、指定视频的评论数。

    注意：统计所有评论（不区分 is_cleaned），即清洗前总数。
    end=None 表示到现在。
    """
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


# ──────────────────────────────────────────────
# Dashboard 图表数据
# ──────────────────────────────────────────────


async def _get_user_video_ids(db: AsyncSession, user_id: str) -> list[str]:
    """获取用户所有分析任务关联的视频 ID（去重）。"""
    rows = await db.execute(
        select(func.distinct(AnalysisTask.video_id)).where(
            AnalysisTask.user_id == user_id
        )
    )
    return [row[0] for row in rows.all()]


async def _get_user_task_ids(db: AsyncSession, user_id: str) -> list[str]:
    """获取用户所有分析任务 ID。"""
    rows = await db.execute(
        select(AnalysisTask.id).where(AnalysisTask.user_id == user_id)
    )
    return [row[0] for row in rows.all()]


async def get_dashboard_trend(
    db: AsyncSession, user_id: str, days: int = 30, granularity: str = "day"
) -> dict:
    """获取评论趋势数据，支持按天或按小时汇总。

    按天：近 N 天每天的评论量
    按小时：近 24 小时每小时的评论量（适合实时追踪场景）

    Returns:
        {labels: [str], values: [int]}
    """
    video_ids = await _get_user_video_ids(db, user_id)
    if not video_ids:
        return {"labels": [], "values": []}

    if granularity == "hour":
        # 近 24 小时，按小时汇总
        cutoff = datetime.utcnow() - timedelta(hours=24)

        rows = await db.execute(
            select(
                func.hour(Comment.create_time).label("h"),
                func.count(Comment.id).label("cnt"),
            )
            .where(
                Comment.video_id.in_(video_ids),
                Comment.create_time >= cutoff,
            )
            .group_by(text("h"))
            .order_by(text("h"))
        )
        hour_map = {}
        for row in rows.all():
            hour_map[row.h] = row.cnt

        labels = []
        values = []
        # 生成完整 24 小时序列
        start_hour = cutoff.hour
        for i in range(24):
            h = (start_hour + i) % 24
            labels.append(f"{h:02d}:00")
            values.append(hour_map.get(h, 0))

        return {"labels": labels, "values": values}

    # 默认：按天汇总
    cutoff = datetime.utcnow() - timedelta(days=days)

    rows = await db.execute(
        select(
            func.date(Comment.create_time).label("day"),
            func.count(Comment.id).label("cnt"),
        )
        .where(
            Comment.video_id.in_(video_ids),
            Comment.create_time >= cutoff,
        )
        .group_by(text("day"))
        .order_by(text("day"))
    )
    day_map = {}
    for row in rows.all():
        day_map[str(row.day)] = row.cnt

    # 生成完整的日期序列（含零值日）
    labels = []
    values = []
    for i in range(days):
        d = cutoff + timedelta(days=i)
        label = d.strftime("%m-%d")
        key = d.strftime("%Y-%m-%d")
        labels.append(label)
        values.append(day_map.get(key, 0))

    return {"labels": labels, "values": values}


async def get_dashboard_sentiment_ratio(db: AsyncSession, user_id: str) -> dict:
    """获取用户所有评论的情感比例分布。

    Returns:
        {positive: int, negative: int, neutral: int}
    """
    video_ids = await _get_user_video_ids(db, user_id)
    if not video_ids:
        return {"positive": 0, "negative": 0, "neutral": 0}

    result = await db.execute(
        select(
            func.sum(case((Comment.sentiment == "positive", 1), else_=0)),
            func.sum(case((Comment.sentiment == "negative", 1), else_=0)),
            func.sum(case((Comment.sentiment == "neutral", 1), else_=0)),
        ).where(Comment.video_id.in_(video_ids))
    )
    pos, neg, neu = result.one()
    return {"positive": pos or 0, "negative": neg or 0, "neutral": neu or 0}


async def get_dashboard_top_topics(
    db: AsyncSession, user_id: str, limit: int = 10
) -> list[dict]:
    """获取用户范围内评论数最多的 TOP N 话题。

    Returns:
        [{topic_name: str, comment_count: int}]
    """
    task_ids = await _get_user_task_ids(db, user_id)
    if not task_ids:
        return []

    result = await db.execute(
        select(Topic.name, func.count(Comment.id).label("cnt"))
        .join(Comment, Comment.topic_id == Topic.id)
        .where(Topic.task_id.in_(task_ids))
        .group_by(Topic.id, Topic.name)
        .order_by(func.count(Comment.id).desc())
        .limit(limit)
    )
    return [{"topic_name": row.name, "comment_count": row.cnt} for row in result.all()]


async def get_dashboard_active_tracking(
    db: AsyncSession, user_id: str
) -> list[dict]:
    """获取当前用户活跃的实时追踪任务列表。

    从 TrackingTask 表 JOIN 获取真实追踪数据（新增评论数、积分余额、运行时长）。

    Returns:
        [{task_id, video_title, platform, author,
          new_comments, credits_remaining, duration_seconds}]
    """
    from backend.models.tracking_task import TrackingTask, TrackingStatus
    from backend.models.user import User

    result = await db.execute(
        select(
            AnalysisTask.id.label("task_id"),
            Video.title.label("video_title"),
            Video.platform,
            Video.uploader_name.label("author"),
            TrackingTask.new_comments_since_start.label("new_comments"),
            TrackingTask.started_at,
            TrackingTask.user_id,
        )
        .select_from(TrackingTask)
        .join(AnalysisTask, TrackingTask.analysis_task_id == AnalysisTask.id)
        .join(Video, TrackingTask.video_id == Video.id)
        .where(
            AnalysisTask.user_id == user_id,
            TrackingTask.status == TrackingStatus.active,
        )
        .order_by(TrackingTask.started_at.desc())
        .limit(5)
    )
    items = []
    now = datetime.utcnow()
    for row in result.all():
        duration = 0
        if row.started_at:
            duration = int((now - row.started_at).total_seconds())

        # 查询用户积分余额
        credits_remaining = 0
        user = await db.get(User, row.user_id)
        if user:
            credits_remaining = user.credits

        items.append({
            "task_id": row.task_id,
            "video_title": row.video_title or "",
            "platform": row.platform.value if hasattr(row.platform, "value") else str(row.platform),
            "author": row.author or "",
            "new_comments": row.new_comments or 0,
            "credits_remaining": credits_remaining,
            "duration_seconds": duration,
        })
    return items


# ──────────────────────────────────────────────
# 头部统计栏
# ──────────────────────────────────────────────


async def get_header_stats(db: AsyncSession, user_id: str) -> dict:
    """获取页面顶部统计栏的 4 个数字。

    Returns:
        {today_comments: int, new_videos: int,
         analysis_completion_rate: int, hot_topic: str}
    """
    now = datetime.utcnow()

    # 今日评论数
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    video_ids = await _get_user_video_ids(db, user_id)
    today_comments = 0
    if video_ids:
        today_comments = await db.scalar(
            select(func.count(Comment.id)).where(
                Comment.video_id.in_(video_ids),
                Comment.create_time >= today_start,
            )
        ) or 0

    # 本月新增视频数
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_videos = await db.scalar(
        select(func.count(func.distinct(AnalysisTask.video_id))).where(
            AnalysisTask.user_id == user_id,
            AnalysisTask.created_at >= month_start,
        )
    ) or 0

    # 分析完成率
    total_tasks = await db.scalar(
        select(func.count(AnalysisTask.id)).where(
            AnalysisTask.user_id == user_id
        )
    ) or 0
    completed = await db.scalar(
        select(func.count(AnalysisTask.id)).where(
            AnalysisTask.user_id == user_id,
            AnalysisTask.status == AnalysisStatus.completed,
        )
    ) or 0
    completion_rate = round(completed / total_tasks * 100) if total_tasks > 0 else 0

    # 热门话题
    task_ids = await _get_user_task_ids(db, user_id)
    hot_topic = "暂无"
    if task_ids:
        hot_name, _ = await _get_hot_topic(db, task_ids)
        hot_topic = hot_name

    return {
        "today_comments": today_comments,
        "new_videos": new_videos,
        "analysis_completion_rate": completion_rate,
        "hot_topic": hot_topic,
    }
