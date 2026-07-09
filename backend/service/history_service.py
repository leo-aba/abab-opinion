"""历史记录 Service — 查询当前用户的分析任务历史列表"""

import logging
import math
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.analysis_task import AnalysisTask, AnalysisStatus, AnalysisMode
from backend.models.video import Video

logger = logging.getLogger("history_service")

# sort_by 前端值 → 模型列映射
_SORT_COLUMN_MAP = {
    "video_title": Video.title,
    "topic_count": AnalysisTask.topic_count,
    "comment_count": AnalysisTask.total_comments_processed,
    "analyzed_at": AnalysisTask.completed_at,
    "created_at": AnalysisTask.created_at,
}

# 默认按创建时间倒序（created_at 始终有值，completed_at 可能为 NULL）
_DEFAULT_SORT_COL = AnalysisTask.created_at


def _get_status_label(status: AnalysisStatus, mode: AnalysisMode) -> str:
    """将任务状态 + 模式转为前端展示标签"""
    if status == AnalysisStatus.completed:
        return "已完成"
    if status == AnalysisStatus.failed:
        return "失败"
    if mode == AnalysisMode.tracking:
        return "追踪中"
    return "处理中"


def _get_time_cutoff(time_range: str | None) -> datetime | None:
    """根据前端时间范围值计算截止时间（数据库无关）。"""
    if not time_range:
        return None
    now = datetime.utcnow()
    mapping = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "3m": timedelta(days=90),
    }
    delta = mapping.get(time_range)
    return now - delta if delta else None


async def get_history_items(
    db: AsyncSession,
    user_id: str,
    *,
    platform: str | None = None,
    time_range: str | None = None,
    keyword: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """查询当前用户的历史分析任务。

    通过 AnalysisTask JOIN Video 联合查询，支持平台/时间/关键词筛选、
    排序、分页。只返回终端状态 (completed / failed) 的任务。

    Returns:
        {
            total: int, total_pages: int, page: int, page_size: int,
            items: [{task_id, video_title, platform, analysis_mode,
                     topic_count, comment_count, analyzed_at, status, status_label}]
        }
    """
    # ── 1. 构建基础查询（显式 JOIN，无 ORM relationship）──
    cols = [
        AnalysisTask.id.label("task_id"),
        Video.title.label("video_title"),
        AnalysisTask.platform,
        AnalysisTask.mode,
        AnalysisTask.topic_count,
        AnalysisTask.total_comments_processed.label("comment_count"),
        AnalysisTask.completed_at.label("analyzed_at"),
        AnalysisTask.created_at.label("created_at"),
        AnalysisTask.status,
    ]

    base_stmt = (
        select(*cols)
        .select_from(AnalysisTask)
        .join(Video, AnalysisTask.video_id == Video.id)
        .where(AnalysisTask.user_id == user_id)
    )

    # ── 2. 可选筛选 ──

    if platform:
        base_stmt = base_stmt.where(AnalysisTask.platform == platform)

    cutoff = _get_time_cutoff(time_range)
    if cutoff:
        base_stmt = base_stmt.where(AnalysisTask.completed_at >= cutoff)

    if keyword:
        base_stmt = base_stmt.where(Video.title.contains(keyword))

    # 仅展示终端状态的任务
    base_stmt = base_stmt.where(
        AnalysisTask.status.in_([AnalysisStatus.completed, AnalysisStatus.failed])
    )

    # ── 3. 统计总数（排序和分页之前）──
    count_stmt = (
        select(func.count())
        .select_from(base_stmt.subquery())
    )
    total = await db.scalar(count_stmt) or 0

    # ── 4. 排序 ──
    order_col = _SORT_COLUMN_MAP.get(sort_by or "", _DEFAULT_SORT_COL)
    if sort_order == "asc":
        base_stmt = base_stmt.order_by(order_col.asc())
    else:
        base_stmt = base_stmt.order_by(order_col.desc())

    # ── 5. 分页 ──
    base_stmt = base_stmt.offset((page - 1) * page_size).limit(page_size)

    # ── 6. 执行 ──
    result = await db.execute(base_stmt)
    rows = result.all()

    # ── 7. 序列化为前端格式 ──
    items = []
    for row in rows:
        row_status: AnalysisStatus = row.status
        row_mode: AnalysisMode = row.mode

        items.append({
            "task_id": row.task_id,
            "video_title": row.video_title or "",
            "platform": row.platform if isinstance(row.platform, str) else "",
            "analysis_mode": row_mode.value if hasattr(row_mode, "value") else str(row_mode),
            "topic_count": row.topic_count or 0,
            "comment_count": row.comment_count or 0,
            "analyzed_at": row.analyzed_at.strftime("%Y-%m-%d %H:%M") if row.analyzed_at else "",
            "created_at": row.created_at.strftime("%Y-%m-%d %H:%M") if row.created_at else "",
            "status": row_status.value if hasattr(row_status, "value") else str(row_status),
            "status_label": _get_status_label(row_status, row_mode),
        })

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

    return {
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "page_size": page_size,
        "items": items,
    }
