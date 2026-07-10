"""评论数据操作 Service — 批量写入、查询"""

import uuid
import logging
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.comment import Comment

logger = logging.getLogger("comment_service")


async def batch_upsert_comments(
    db: AsyncSession,
    video_id: str,
    platform: str,
    comments: list[dict],
    task_id: str | None = None,
    is_cleaned: bool = False,
) -> int:
    """批量写入评论，cid+platform 联合唯一防重复。

    使用 INSERT IGNORE 确保数据库层面的幂等性，配合 Python 层批次内去重。

    Args:
        db: 数据库 session
        video_id: 视频 UUID
        platform: 平台标识（bilibili / douyin）
        comments: 评论列表，每项格式：
            {cid, text, create_time, digg_count, reply_comment_total,
             user:{uid, nickname, avatar}}
        task_id: 关联的分析任务 ID（可空）

    Returns:
        int: 实际写入的评论条数
    """
    if not comments:
        return 0

    # 1) 批次内去重
    seen_cids: set[str] = set()
    unique_comments: list[dict] = []
    for c in comments:
        cid = c["cid"]
        if cid in seen_cids:
            continue
        seen_cids.add(cid)
        unique_comments.append(c)

    if not unique_comments:
        return 0

    # 2) 构建 INSERT IGNORE 语句（使用数据库列名）
    from datetime import datetime
    now = datetime.utcnow()
    values = []
    for c in unique_comments:
        user_info = c.get("user", {})
        values.append({
            "id": str(uuid.uuid4()),
            "platform_comment_id": c["cid"],
            "video_id": video_id,
            "task_id": task_id,
            "content": c.get("text", ""),
            "publish_time": c.get("create_time"),
            "like_count": c.get("digg_count", 0),
            "reply_count": c.get("reply_comment_total", 0),
            "user_uid": user_info.get("uid"),
            "author_name": user_info.get("nickname"),
            "author_avatar": user_info.get("avatar"),
            "platform": platform,
            "is_cleaned": is_cleaned,
            "fetched_at": now,
        })

    stmt = insert(Comment).prefix_with("IGNORE").values(values)
    result = await db.execute(stmt)
    await db.flush()

    inserted = result.rowcount
    logger.info(
        "评论批量写入: video=%s, platform=%s, 提交=%d, 跳过=%d",
        video_id, platform, inserted, len(comments) - inserted,
    )
    return inserted


async def delete_comments_by_video(db: AsyncSession, video_id: str) -> int:
    """删除指定视频的所有评论。

    Args:
        db: 数据库 session
        video_id: 视频 UUID

    Returns:
        int: 删除的评论条数
    """
    result = await db.execute(
        delete(Comment).where(Comment.video_id == video_id)
    )
    await db.flush()
    logger.info("已删除视频 %s 的 %d 条评论", video_id, result.rowcount)
    return result.rowcount


async def mark_comments_cleaned(
    db: AsyncSession,
    video_id: str,
    cleaned_cids: list[str],
    task_id: str,
) -> int:
    """标记清洗后的评论：设置 is_cleaned=1 并关联 task_id。

    用于评论流水线改造后：先批量插入所有原始评论（is_cleaned=0），
    清洗后通过此函数 UPDATE 通过清洗的子集。

    Args:
        db: 数据库 session
        video_id: 视频 UUID
        cleaned_cids: 通过清洗的评论的 platform_comment_id 列表
        task_id: 关联的分析任务 ID

    Returns:
        int: 实际更新的行数
    """
    if not cleaned_cids:
        return 0

    from sqlalchemy import update
    from backend.models.comment import Comment

    stmt = (
        update(Comment)
        .where(
            Comment.video_id == video_id,
            Comment.cid.in_(cleaned_cids),
        )
        .values(is_cleaned=True, task_id=task_id)
    )
    result = await db.execute(stmt)
    await db.flush()

    updated = result.rowcount
    logger.info(
        "标记清洗评论: video=%s, 提交=%d, 实际更新=%d",
        video_id, len(cleaned_cids), updated,
    )
    return updated
