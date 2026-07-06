"""评论数据操作 Service — 批量写入、查询"""

import uuid
import logging
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.comment import Comment

logger = logging.getLogger("comment_service")


async def batch_upsert_comments(
    db: AsyncSession,
    video_id: str,
    platform: str,
    comments: list[dict],
    task_id: str | None = None,
) -> int:
    """批量写入评论，cid+platform 联合唯一防重复。

    Args:
        db: 数据库 session
        video_id: 视频 UUID
        platform: 平台标识（bilibili / douyin）
        comments: 评论列表，每项格式：
            {cid, text, create_time, digg_count, reply_comment_total,
             user:{uid, nickname, avatar}}
        task_id: 关联的分析任务 ID（可空）

    Returns:
        int: 实际新增的评论条数
    """
    if not comments:
        return 0

    # 1) 查询已存在的 cid 集合（避免逐条查）
    cid_list = [c["cid"] for c in comments]
    existing_result = await db.execute(
        select(Comment.cid).where(
            Comment.platform == platform,
            Comment.cid.in_(cid_list),
        )
    )
    existing_cids = {row[0] for row in existing_result.fetchall()}

    # 2) 过滤出新增的评论
    new_comments = []
    for c in comments:
        if c["cid"] in existing_cids:
            continue
        user_info = c.get("user", {})
        new_comments.append(
            Comment(
                id=str(uuid.uuid4()),
                cid=c["cid"],
                video_id=video_id,
                task_id=task_id,
                text=c.get("text", ""),
                create_time=c.get("create_time", 0),
                digg_count=c.get("digg_count", 0),
                reply_comment_total=c.get("reply_comment_total", 0),
                user_uid=user_info.get("uid"),
                user_nickname=user_info.get("nickname"),
                user_avatar=user_info.get("avatar"),
                platform=platform,
            )
        )

    if not new_comments:
        return 0

    # 3) 批量插入
    db.add_all(new_comments)
    await db.flush()

    logger.info(
        "评论批量写入: video=%s, platform=%s, 新增=%d, 跳过=%d",
        video_id, platform, len(new_comments), len(comments) - len(new_comments),
    )
    return len(new_comments)


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
