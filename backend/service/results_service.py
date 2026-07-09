"""分析结果 Service — 查询 Task/Topic/Comment/Video 数据组装结果"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.analysis_task import AnalysisTask
from backend.models.video import Video
from backend.models.topic import Topic
from backend.models.comment import Comment
from backend.service.video_service import _download_cover

logger = logging.getLogger("results_service")


# ──────────────────────────────────────────────
# 概览
# ──────────────────────────────────────────────


async def get_overview(db: AsyncSession, task_id: str) -> dict:
    """获取分析概览数据。

    Returns:
        {video_title, video_cover, video_uploader, video_platform, video_url,
         video_view_count, video_like_count, video_publish_time,
         total_comments, topic_count, positive_pct, negative_pct, neutral_pct}
    """
    # 查 task + 关联 video
    task = await db.get(AnalysisTask, task_id)
    if not task:
        raise ValueError("任务不存在")

    video = await db.get(Video, task.video_id)

    # ── 封面：远程 URL → 下载到本地（懒修复旧数据）──
    cover_url = video.cover_url if video else ""
    if cover_url and cover_url.startswith("http"):
        try:
            local = await _download_cover(cover_url)
            if local:
                cover_url = local
                # 持久化本地路径，下次直接读取
                if video:
                    video.cover_url = local
                    await db.commit()
        except Exception:
            pass  # 下载失败保留远程 URL，前端 onerror 兜底

    # ── 视频基础信息 ──
    video_info = {
        "video_title": video.title if video else "",
        "video_cover": cover_url,
        "video_uploader": video.uploader_name if video else "",
        "video_platform": video.platform.value if video and hasattr(video.platform, 'value') else str(video.platform) if video else "",
        "video_url": video.url if video else "",
        "video_view_count": video.view_count or 0 if video else 0,
        "video_like_count": video.like_count or 0 if video else 0,
        "video_publish_time": video.publish_time.strftime("%Y-%m-%d") if video and video.publish_time else "",
    }

    # 评论总数
    total = await db.scalar(
        select(func.count(Comment.id)).where(Comment.task_id == task_id)
    ) or 0

    # 话题数
    topic_count = task.topic_count or 0

    # 情感占比：从 topics 表的 sentient_distribution_json 汇总
    positive_pct = 0.0
    negative_pct = 0.0
    neutral_pct = 0.0

    if total > 0 and topic_count > 0:
        topics_result = await db.execute(
            select(Topic.sentiment_distribution_json).where(Topic.task_id == task_id)
        )
        pos_total = neg_total = neu_total = 0
        for row in topics_result.scalars().all():
            if not row:
                continue
            try:
                dist = json.loads(row) if isinstance(row, str) else row
                pos_total += dist.get("positive", 0)
                neg_total += dist.get("negative", 0)
                neu_total += dist.get("neutral", 0)
            except (json.JSONDecodeError, TypeError):
                continue

        # 用 comment 级别的 sentiment 兜底
        if pos_total + neg_total + neu_total == 0:
            sentiment_result = await db.execute(
                select(
                    func.sum(case((Comment.sentiment == "positive", 1), else_=0)),
                    func.sum(case((Comment.sentiment == "negative", 1), else_=0)),
                    func.sum(case((Comment.sentiment == "neutral", 1), else_=0)),
                ).where(Comment.task_id == task_id)
            )
            pos_total, neg_total, neu_total = sentiment_result.one()
            pos_total = pos_total or 0
            neg_total = neg_total or 0
            neu_total = neu_total or 0
        else:
            neu_total += max(0, total - pos_total - neg_total - neu_total)

        grand = pos_total + neg_total + neu_total
        if grand > 0:
            positive_pct = round(pos_total / grand * 100, 1)
            negative_pct = round(neg_total / grand * 100, 1)
            neutral_pct = round(neu_total / grand * 100, 1)

    return {
        **video_info,
        "total_comments": total,
        "topic_count": topic_count,
        "positive_pct": positive_pct,
        "negative_pct": negative_pct,
        "neutral_pct": neutral_pct,
    }


# ──────────────────────────────────────────────
# 情感占比（单独接口，供饼图用）
# ──────────────────────────────────────────────


async def get_sentiment_ratio(db: AsyncSession, task_id: str) -> dict:
    """获取情感比例分布。

    优先从 topics 表的 sentiment_distribution_json 汇总（LLM 分析结果），
    确保正/负/中性三分类齐全。若无 topic 数据，回退到 comment 级别统计。

    Returns:
        {positive: int, negative: int, neutral: int}
    """
    pos_total = 0
    neg_total = 0
    neu_total = 0

    # 从 topics 表聚合 LLM 生成的情感分布（含正确的中性计数）
    topics_result = await db.execute(
        select(Topic.sentiment_distribution_json).where(Topic.task_id == task_id)
    )
    for row in topics_result.scalars().all():
        if not row:
            continue
        try:
            dist = json.loads(row) if isinstance(row, str) else row
            pos_total += dist.get("positive", 0)
            neg_total += dist.get("negative", 0)
            neu_total += dist.get("neutral", 0)
        except (json.JSONDecodeError, TypeError):
            continue

    # 若无 topic 数据，回退到 comment 级别统计
    if pos_total + neg_total + neu_total == 0:
        result = await db.execute(
            select(
                func.sum(case((Comment.sentiment == "positive", 1), else_=0)),
                func.sum(case((Comment.sentiment == "negative", 1), else_=0)),
                func.sum(case((Comment.sentiment == "neutral", 1), else_=0)),
            ).where(Comment.task_id == task_id)
        )
        pos, neg, neu = result.one()
        pos_total = pos or 0
        neg_total = neg or 0
        neu_total = neu or 0

    return {
        "positive": pos_total,
        "negative": neg_total,
        "neutral": neu_total,
    }


# ──────────────────────────────────────────────
# 话题列表
# ──────────────────────────────────────────────


async def get_topics_list(db: AsyncSession, task_id: str) -> list[dict]:
    """获取话题列表（简版，只有名称和评论数）。

    Returns:
        [{topic_name: str, comment_count: int}]
    """
    result = await db.execute(
        select(Topic.name, Topic.comment_count)
        .where(Topic.task_id == task_id)
        .order_by(Topic.comment_count.desc())
    )
    return [
        {"topic_name": row.name, "comment_count": row.comment_count}
        for row in result.all()
    ]


# ──────────────────────────────────────────────
# 话题详情
# ──────────────────────────────────────────────


async def get_topic_detail(db: AsyncSession, task_id: str, topic_name: str) -> dict:
    """获取单个话题的详细信息。

    Returns:
        {topic_name, comment_count, percentage, sample_comments, keywords, ai_summary}
    """
    # 按 topic_name 查找（同一 task 内 topic name 唯一）
    result = await db.execute(
        select(Topic).where(
            and_(Topic.task_id == task_id, Topic.name == topic_name)
        )
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise ValueError(f"话题不存在: {topic_name}")

    # 示例评论（最多 5 条）
    comments_result = await db.execute(
        select(Comment.text)
        .where(Comment.topic_id == topic.id)
        .limit(5)
    )
    sample_comments = [row[0] for row in comments_result.all()]

    # 解析 keywords
    keywords = []
    if topic.keywords_json:
        try:
            keywords = json.loads(topic.keywords_json) if isinstance(topic.keywords_json, str) else topic.keywords_json
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "topic_name": topic.name,
        "comment_count": topic.comment_count,
        "percentage": topic.percentage,
        "sample_comments": sample_comments,
        "keywords": keywords,
        "ai_summary": topic.ai_summary or "",
    }


# ──────────────────────────────────────────────
# AI 总结
# ──────────────────────────────────────────────


async def get_ai_summary(db: AsyncSession, task_id: str) -> dict:
    """获取 AI 生成的综合分析总结。

    Returns:
        {title: str, summary_text: str, highlights: [{label, text}]}
    """
    task = await db.get(AnalysisTask, task_id)
    if not task:
        raise ValueError("任务不存在")

    video = await db.get(Video, task.video_id)
    title = f"{video.title} - 分析总结" if video else "分析总结"

    summary_text = ""
    highlights = []

    if task.error_message:
        try:
            error_data = json.loads(task.error_message) if isinstance(task.error_message, str) else task.error_message
            summary_text = error_data.get("ai_summary", "")
        except (json.JSONDecodeError, TypeError):
            pass

    # 从话题列表生成 highlights（话题名 + 关键词作为要点）
    if task.topic_count and task.topic_count > 0:
        topics_result = await db.execute(
            select(Topic.name, Topic.keywords_json, Topic.comment_count)
            .where(Topic.task_id == task_id)
            .order_by(Topic.comment_count.desc())
        )
        for row in topics_result.all():
            kw_str = ""
            if row.keywords_json:
                try:
                    kws = json.loads(row.keywords_json) if isinstance(row.keywords_json, str) else row.keywords_json
                    kw_str = "、".join(kws[:3])
                except (json.JSONDecodeError, TypeError):
                    pass
            highlights.append({
                "label": row.name,
                "text": f"({row.comment_count} 条评论)" + (f" 关键词: {kw_str}" if kw_str else ""),
            })

    return {
        "title": title,
        "summary_text": summary_text,
        "highlights": highlights,
    }


# ──────────────────────────────────────────────
# 评论搜索
# ──────────────────────────────────────────────


async def search_comments(
    db: AsyncSession,
    task_id: str,
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """搜索评论（关键词 + 分页）。

    Returns:
        {total: int, items: [{text, platform, time_ago, topic, likes, highlighted_text}]}
    """
    # 基础查询
    base_stmt = select(Comment).where(Comment.task_id == task_id)

    if keyword:
        base_stmt = base_stmt.where(Comment.text.contains(keyword))

    # 总数
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = await db.scalar(count_stmt) or 0
    total = total if isinstance(total, int) else 0

    # 分页
    stmt = base_stmt.order_by(Comment.digg_count.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await db.execute(stmt)
    comments = result.scalars().all()

    # 批量查 topic 名称
    topic_ids = {c.topic_id for c in comments if c.topic_id}
    topic_map = {}
    if topic_ids:
        topics_result = await db.execute(
            select(Topic.id, Topic.name).where(Topic.id.in_(topic_ids))
        )
        topic_map = {row.id: row.name for row in topics_result.all()}

    now = datetime.now(timezone.utc)

    items = []
    for c in comments:
        # 相对时间
        time_ago = ""
        if c.create_time:
            delta = now - c.create_time.replace(tzinfo=timezone.utc)
            days = delta.days
            if days > 365:
                time_ago = f"{days // 365} 年前"
            elif days > 30:
                time_ago = f"{days // 30} 月前"
            elif days > 0:
                time_ago = f"{days} 天前"
            elif delta.seconds > 3600:
                time_ago = f"{delta.seconds // 3600} 小时前"
            elif delta.seconds > 60:
                time_ago = f"{delta.seconds // 60} 分钟前"
            else:
                time_ago = "刚刚"

        # 关键词高亮
        highlighted_text = c.text or ""
        if keyword:
            highlighted_text = highlighted_text.replace(
                keyword, f"<mark>{keyword}</mark>"
            )

        items.append({
            "text": c.text or "",
            "highlighted_text": highlighted_text,
            "platform": c.platform or "",
            "time_ago": time_ago,
            "topic": topic_map.get(c.topic_id, ""),
            "likes": c.digg_count,
        })

    return {"total": total, "items": items}


# ──────────────────────────────────────────────
# 时间趋势
# ──────────────────────────────────────────────

# 旭日图配色（最多 8 个话题）
_SUNBURST_COLORS = [
    '#FF7A22', '#00B4CC', '#FFD23F', '#7B61FF',
    '#44D7B6', '#FF6B6B', '#4ECDC4', '#F7B731',
]


def _date_trunc(column, granularity: str):
    """根据粒度返回 MySQL 日期截断表达式。"""
    if granularity == 'hour':
        return func.date_format(column, '%Y-%m-%d %H:00')
    elif granularity == 'week':
        # yearweek 返回如 202628，取每周一
        return func.date_format(
            func.str_to_date(func.concat(func.yearweek(column), ' Monday'), '%X%V %W'),
            '%Y-%m-%d'
        )
    else:  # day (default)
        return func.date(column)


async def get_trend(
    db: AsyncSession, task_id: str, granularity: str = 'day'
) -> dict:
    """获取评论数量趋势（概览 Tab 单线图）。

    Returns:
        {labels: [str], values: [int]}
    """
    date_col = _date_trunc(Comment.create_time, granularity)

    result = await db.execute(
        select(
            date_col.label('dt'),
            func.count(Comment.id).label('cnt'),
        )
        .where(Comment.task_id == task_id, Comment.create_time.isnot(None))
        .group_by('dt')
        .order_by('dt')
    )
    rows = result.all()

    return {
        "labels": [str(row.dt) for row in rows],
        "values": [row.cnt for row in rows],
    }


async def get_trends_detail(
    db: AsyncSession, task_id: str, granularity: str = 'day'
) -> dict:
    """获取分情感的趋势详情（多线图：正面/负面/总计）。

    Returns:
        {labels: [str], datasets: [{label, values, color}]}
    """
    date_col = _date_trunc(Comment.create_time, granularity)

    result = await db.execute(
        select(
            date_col.label('dt'),
            func.count(Comment.id).label('total'),
            func.sum(case((Comment.sentiment == 'positive', 1), else_=0)).label('pos'),
            func.sum(case((Comment.sentiment == 'negative', 1), else_=0)).label('neg'),
        )
        .where(Comment.task_id == task_id, Comment.create_time.isnot(None))
        .group_by('dt')
        .order_by('dt')
    )
    rows = result.all()

    labels = [str(row.dt) for row in rows]

    return {
        "labels": labels,
        "datasets": [
            {"label": "总计", "values": [row.total for row in rows], "color": "#7B61FF"},
            {"label": "正面", "values": [row.pos or 0 for row in rows], "color": "#00B4CC"},
            {"label": "负面", "values": [row.neg or 0 for row in rows], "color": "#FF7A22"},
        ],
    }


# ──────────────────────────────────────────────
# 属性情感（LLM aspects）
# ──────────────────────────────────────────────


def _lighten(hex_color: str, factor: float = 0.4) -> str:
    """把 hex 颜色变亮。factor: 0=不变, 1=全白。"""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return f'#{r:02x}{g:02x}{b:02x}'


def _darken(hex_color: str, factor: float = 0.4) -> str:
    """把 hex 颜色变暗。"""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = max(0, int(r * (1 - factor)))
    g = max(0, int(g * (1 - factor)))
    b = max(0, int(b * (1 - factor)))
    return f'#{r:02x}{g:02x}{b:02x}'


async def get_sentiment_attribute(db: AsyncSession, task_id: str) -> dict:
    """获取属性情感数据（旭日图 + 雷达图）。

    从 LLM 分析结果中读取 aspects（评价维度），每个维度拆分为
    正面/中性/负面三个扇区，同一维度同色系深浅区分。

    Returns:
        {sunburst: [{label, value, color}], radar: {labels, positive_scores, negative_scores}}
    """
    task = await db.get(AnalysisTask, task_id)
    if not task:
        return _empty_sentiment_attribute()

    aspects = []
    if task.error_message:
        try:
            error_data = json.loads(task.error_message) if isinstance(task.error_message, str) else task.error_message
            aspects = error_data.get("aspects", [])
        except (json.JSONDecodeError, TypeError):
            pass

    if not aspects:
        return _empty_sentiment_attribute()

    sunburst = []
    radar_labels = []
    radar_positive = []
    radar_negative = []

    for i, asp in enumerate(aspects):
        name = asp.get("name", "")
        pos = int(asp.get("positive", 0))
        neg = int(asp.get("negative", 0))
        neu = int(asp.get("neutral", 0))
        total = pos + neg + neu

        # 基础颜色，同维度正面/中性/负面用同色系深浅区分
        base = _SUNBURST_COLORS[i % len(_SUNBURST_COLORS)]

        for suffix, value, color in zip(
            [" 正面", " 中性", " 负面"], [pos, neu, neg],
            [_lighten(base, 0.25), base, _darken(base, 0.30)]
        ):
            if value > 0:
                sunburst.append({
                    "label": f"{name}{suffix}",
                    "value": value,
                    "color": color,
                })

        # 雷达图：正/负面占比归一化到 0-5
        if total > 0:
            radar_positive.append(round(pos / total * 5, 1))
            radar_negative.append(round(neg / total * 5, 1))
        else:
            radar_positive.append(0)
            radar_negative.append(0)
        radar_labels.append(name)

    return {
        "sunburst": sunburst,
        "radar": {
            "labels": radar_labels,
            "positive_scores": radar_positive,
            "negative_scores": radar_negative,
        },
    }


def _empty_sentiment_attribute() -> dict:
    return {
        "sunburst": [],
        "radar": {"labels": [], "positive_scores": [], "negative_scores": []},
    }
