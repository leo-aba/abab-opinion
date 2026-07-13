"""追踪任务 Service — 创建、调度、轮询追踪任务

实时追踪模式：分析完成后每 120 秒自动抓取平台最新评论，
增量写入 DB（INSERT IGNORE），清洗并标记，消耗积分。
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_sessionmaker
from backend.models.analysis_task import AnalysisTask, AnalysisMode
from backend.models.tracking_task import TrackingTask, TrackingStatus
from backend.models.topic import Topic
from backend.models.video import Video
from backend.models.comment import Comment
from backend.models.user import User
from backend.service.video_service import (
    fetch_bilibili_comment_page,
    fetch_douyin_comments,
    _extract_bilibili_comment_info,
)
from backend.service.comment_service import batch_upsert_comments, mark_comments_cleaned
from backend.service.comment_cleaner import clean_comments
from backend.service.llm_service import classify_new_comments_with_llm

logger = logging.getLogger("tracking_service")

# ──────────────────────────────────────────────
# 模块级状态
# ──────────────────────────────────────────────

# 活跃追踪任务注册表: tracking_id → asyncio.Task
_active_trackings: dict[str, asyncio.Task] = {}

# 默认轮询间隔（秒）
DEFAULT_POLL_INTERVAL = 10

# 每轮最多抓取的页数（防单次耗时过长）
MAX_POLL_PAGES = 5

# 连续失败次数上限（超过则停止追踪）
MAX_CONSECUTIVE_FAILURES = 5

# ── LLM 增量分析配置 ──

# 最小分析间隔（秒）
ANALYSIS_INTERVAL_SECONDS = 60

# 连续 LLM 分析失败上限（超过后继续轮询但不分析）
MAX_ANALYSIS_FAILURES = 10


# ──────────────────────────────────────────────
# 增量评论抓取
# ──────────────────────────────────────────────


async def _fetch_new_comments(
    platform: str,
    platform_video_id: str,
    last_comment_id: str | None,
    extras: dict | None = None,
) -> list[dict]:
    """增量抓取新评论：从平台 API 抓取页面直到遇到已知的 last_comment_id。

    Args:
        platform: 平台标识（bilibili / douyin）
        platform_video_id: 平台侧视频 ID（B站为 aid，抖音为 aweme_id）
        last_comment_id: 上次抓取的最后一个评论 cid。None 表示无历史（首次抓取）。
        extras: 视频 extras 元数据

    Returns:
        list[dict]: 新评论列表（格式与 batch_upsert_comments 兼容）
    """
    if platform == "bilibili":
        return await _fetch_new_bilibili_comments(platform_video_id, last_comment_id, extras)
    elif platform == "douyin":
        return await _fetch_new_douyin_comments(platform_video_id, last_comment_id)
    else:
        logger.warning("不支持的平台: %s", platform)
        return []


async def _fetch_new_bilibili_comments(
    aid_str: str,
    last_comment_id: str | None,
    extras: dict | None = None,
) -> list[dict]:
    """增量抓取 B站新评论。

    逐页抓取直到：遇到 last_comment_id、到达末尾、或达到 MAX_POLL_PAGES。
    """
    try:
        aid = int(aid_str)
    except (ValueError, TypeError):
        logger.error("Invalid B站 aid: %s", aid_str)
        return []

    new_comments: list[dict] = []
    cursor = 0
    seen_last = False

    for page in range(MAX_POLL_PAGES):
        try:
            # mode=2 按时间排序，确保新评论排在前面，增量游标逻辑正确
            replies, next_cursor, is_end = await fetch_bilibili_comment_page(aid, cursor, mode=2)
        except Exception as e:
            logger.error("B站评论抓取第 %d 页失败: %s", page + 1, e)
            break

        if replies is None or not replies:
            break

        for c in replies:
            cid = str(c.get("rpid", ""))
            if last_comment_id and cid == last_comment_id:
                seen_last = True
                break
            new_comments.append(_extract_bilibili_comment_info(c))

        if seen_last or is_end:
            break

        cursor = next_cursor if next_cursor is not None else cursor
        await asyncio.sleep(1.0)  # 防限流

    logger.info(
        "B站增量抓取: 抓了 %d 页, 新评论 %d 条, last_comment_id=%s",
        page + 1, len(new_comments), last_comment_id,
    )
    return list(reversed(new_comments))  # 反转使评论按时间正序（旧→新）


async def _fetch_new_douyin_comments(
    aweme_id: str,
    last_comment_id: str | None,
) -> list[dict]:
    """增量抓取抖音新评论。

    抖音 API 返回时间倒序评论，抓取直到遇到 last_comment_id 或达到上限。
    """
    try:
        raw_comments = await fetch_douyin_comments(
            aweme_id, max_count=MAX_POLL_PAGES * 20,
        )
    except Exception as e:
        logger.error("抖音评论增量抓取失败: %s", e)
        return []

    new_comments: list[dict] = []
    for c in raw_comments:
        cid = str(c.get("cid", ""))
        if last_comment_id and cid == last_comment_id:
            break
        new_comments.append(c)

    logger.info(
        "抖音增量抓取: 新评论 %d 条, last_comment_id=%s",
        len(new_comments), last_comment_id,
    )
    # 抖音 API 返回最新优先，反转为旧→新，与 B站路径对齐
    # 确保调用方 new_raw[-1] 始终拿到最新评论作为下次游标
    return list(reversed(new_comments))


# ──────────────────────────────────────────────
# 增量 LLM 分析辅助函数
# ──────────────────────────────────────────────


async def _get_unanalyzed_cleaned_comments(
    db: AsyncSession,
    video_id: str,
    last_analyzed_comment_id: str | None,
) -> list[Comment]:
    """查询已清洗但尚未 LLM 分析过的评论（按发布时间升序）。

    通过 Comment.sentiment IS NULL 判断未分析，无需依赖游标参数。
    last_analyzed_comment_id 保留用于未来可能的增量游标优化。
    """
    from sqlalchemy import and_

    result = await db.execute(
        select(Comment)
        .where(
            and_(
                Comment.video_id == video_id,
                Comment.is_cleaned == True,
                Comment.sentiment.is_(None),  # 未分析过的评论 sentiment 为 NULL
            )
        )
        .order_by(Comment.create_time.asc())
        .limit(100)  # 单次最多分析 100 条，防止 LLM 超时
    )
    return list(result.scalars().all())


async def _get_existing_topics(
    db: AsyncSession,
    analysis_task_id: str,
) -> list[dict]:
    """获取已有话题列表（name + keywords）。"""
    result = await db.execute(
        select(Topic.name, Topic.keywords_json).where(
            Topic.task_id == analysis_task_id,
        )
    )
    topics = []
    for row in result.all():
        keywords = []
        if row.keywords_json:
            try:
                keywords = json.loads(row.keywords_json)
            except (json.JSONDecodeError, TypeError):
                pass
        topics.append({"name": row.name, "keywords": keywords})
    return topics


async def _ensure_other_topic(
    db: AsyncSession,
    analysis_task_id: str,
    video_id: str,
) -> Topic:
    """获取或创建「其他」话题。"""
    result = await db.execute(
        select(Topic).where(
            Topic.task_id == analysis_task_id,
            Topic.name == "其他",
        )
    )
    topic = result.scalar_one_or_none()
    if topic is None:
        topic = Topic(
            id=str(uuid.uuid4()),
            task_id=analysis_task_id,
            video_id=video_id,
            name="其他",
            comment_count=0,
            percentage=0.0,
            keywords_json="[]",
            ai_summary="追踪期间无法归类到已有话题的新增评论",
            sentiment_distribution_json=json.dumps({"positive": 0, "negative": 0, "neutral": 0}),
        )
        db.add(topic)
        await db.flush()
        logger.info("已创建「其他」话题: topic_id=%s", topic.id)
    return topic


async def _apply_classification_results(
    db: AsyncSession,
    unanalyzed_comments: list[Comment],
    llm_result: dict,
    existing_topics: list[dict],
    analysis_task_id: str,
    video_id: str,
) -> int:
    """将 LLM 分类结果写回 Comment 和 Topic。

    Args:
        db: 数据库 session
        unanalyzed_comments: 未分析的评论 ORM 对象列表
        llm_result: classify_new_comments_with_llm 返回的 dict
        existing_topics: 已有话题列表
        analysis_task_id: 分析任务 ID
        video_id: 视频 ID

    Returns:
        int: 成功分类的评论数
    """
    assignments = llm_result.get("assignments", [])
    if not assignments:
        return 0

    # 1) 建立已有话题名 → Topic ORM 的映射
    topic_map: dict[str, Topic] = {}
    for t in existing_topics:
        name = t.get("name", "")
        result = await db.execute(
            select(Topic).where(
                Topic.task_id == analysis_task_id,
                Topic.name == name,
            )
        )
        topic = result.scalar_one_or_none()
        if topic:
            # 标准化 key（去空格、小写）
            topic_map[name.strip().lower()] = topic
            topic_map[name.strip()] = topic

    # 2) 遍历 assignment，逐条更新 Comment 和 Topic
    classified = 0
    for assignment in assignments:
        idx = assignment.get("comment_index", -1)
        topic_name = assignment.get("topic_name", "其他")
        sentiment = assignment.get("sentiment", "neutral")

        # 校验 sentiment 合法性
        if sentiment not in ("positive", "negative", "neutral"):
            sentiment = "neutral"

        # 校验索引
        if not isinstance(idx, int) or idx < 0 or idx >= len(unanalyzed_comments):
            logger.warning("增量分类: 无效 comment_index=%s, 跳过", idx)
            continue

        comment = unanalyzed_comments[idx]

        # 3) 查找匹配的 Topic
        topic_name_clean = topic_name.strip()
        topic = (
            topic_map.get(topic_name_clean.lower())
            or topic_map.get(topic_name_clean)
        )

        if topic is None and topic_name_clean != "其他":
            # 尝试部分匹配（话题名包含关系）
            for key, t in topic_map.items():
                if topic_name_clean in key or key in topic_name_clean:
                    topic = t
                    break

        if topic is None:
            # 归入「其他」
            topic = await _ensure_other_topic(db, analysis_task_id, video_id)

        # 4) 更新 Comment
        comment.sentiment = sentiment
        comment.topic_id = topic.id

        # 5) 增量更新 Topic.sentiment_distribution_json 和 comment_count
        dist = {"positive": 0, "negative": 0, "neutral": 0}
        if topic.sentiment_distribution_json:
            try:
                dist.update(json.loads(topic.sentiment_distribution_json))
            except (json.JSONDecodeError, TypeError):
                pass
        dist[sentiment] = dist.get(sentiment, 0) + 1
        topic.sentiment_distribution_json = json.dumps(dist)
        topic.comment_count = (topic.comment_count or 0) + 1

        classified += 1

    # 6) 重新计算所有 Topic 的 percentage
    all_topics_result = await db.execute(
        select(Topic).where(Topic.task_id == analysis_task_id)
    )
    all_topics = all_topics_result.scalars().all()
    total_comments = sum(t.comment_count or 0 for t in all_topics)
    if total_comments > 0:
        for t in all_topics:
            t.percentage = round((t.comment_count or 0) / total_comments * 100, 1)

    logger.info("增量分类写回完成: %d/%d 条已分类", classified, len(assignments))
    return classified


# ──────────────────────────────────────────────
# 轮询循环
# ──────────────────────────────────────────────


async def poll_tracking_comments(tracking_id: str) -> None:
    """主轮询协程：每 10s 检查新评论并写入 DB。

    由 start_tracking() 通过 asyncio.create_task 启动。
    循环退出条件（三重保护）：
    1. 被 asyncio cancel
    2. DB 中 status 非 active
    3. 不在 _active_trackings 注册表中（被 stop_tracking 移除）
    """
    logger.info("追踪轮询启动: tracking_id=%s", tracking_id)

    consecutive_failures = 0
    consecutive_analysis_failures = 0
    sessionmaker = get_sessionmaker()

    try:
        while True:
            # 0) 三重保护：检查注册表 — 如果被 stop_tracking 移除了，立即退出
            if tracking_id not in _active_trackings:
                logger.info("追踪轮询已被注销（不在注册表中）: tracking_id=%s", tracking_id)
                break

            try:
                async with sessionmaker() as db:
                    # 1) 加载追踪任务
                    tracking = await db.get(TrackingTask, tracking_id)
                    if tracking is None or tracking.status != TrackingStatus.active:
                        logger.info("追踪任务已停止: tracking_id=%s, status=%s",
                                     tracking_id, tracking.status if tracking else "None")
                        break

                    # 2) 加载关联数据
                    analysis_task = await db.get(AnalysisTask, tracking.analysis_task_id)
                    if analysis_task is None:
                        logger.error("关联分析任务不存在: %s", tracking.analysis_task_id)
                        tracking.status = TrackingStatus.stopped
                        await db.commit()
                        break

                    video = await db.get(Video, tracking.video_id)
                    if video is None:
                        logger.error("关联视频不存在: %s", tracking.video_id)
                        tracking.status = TrackingStatus.stopped
                        await db.commit()
                        break

                    # 3) 积分消耗计算（按实际经过时间）
                    now = datetime.utcnow()
                    if tracking.last_poll_at:
                        elapsed_hours = (now - tracking.last_poll_at).total_seconds() / 3600.0
                    else:
                        elapsed_hours = (now - tracking.started_at).total_seconds() / 3600.0

                    credit_cost = elapsed_hours * tracking.credits_rate_per_hour

                    # 4) 检查积分余额
                    user = await db.get(User, tracking.user_id)
                    if user is None:
                        logger.error("用户不存在: %s", tracking.user_id)
                        tracking.status = TrackingStatus.stopped
                        await db.commit()
                        break

                    if user.credits < credit_cost:
                        logger.warning("积分不足: user=%s, 需要=%.1f, 余额=%d",
                                        user.username, credit_cost, user.credits)
                        tracking.status = TrackingStatus.exhausted
                        tracking.stopped_at = now
                        await db.commit()
                        break

                    # 扣减积分
                    user.credits = max(0, int(user.credits - credit_cost))
                    tracking.credits_consumed = tracking.credits_consumed + credit_cost
                    tracking.last_poll_at = now

                    # 5) 增量抓取新评论
                    platform = analysis_task.platform
                    if hasattr(platform, 'value'):
                        platform = platform.value
                    platform_video_id = video.platform_video_id
                    extras = video.extras if video.extras else {}

                    # B站的 platform_video_id 是 BV 号，需要 aid 来抓取评论
                    if platform == "bilibili":
                        fetch_id = str(extras.get("aid", platform_video_id))
                    else:
                        fetch_id = platform_video_id

                    new_raw = await _fetch_new_comments(
                        platform=platform,
                        platform_video_id=fetch_id,
                        last_comment_id=tracking.last_comment_id,
                        extras=extras,
                    )

                    if new_raw:
                        # 6a) 写入原始评论（is_cleaned=False, task_id 关联到原分析任务）
                        inserted = await batch_upsert_comments(
                            db, tracking.video_id, platform,
                            new_raw, task_id=analysis_task.id, is_cleaned=False,
                        )
                        logger.info("追踪轮询写入 %d 条新原始评论", inserted)

                        # 6b) 清洗
                        cleaned, clean_stats = clean_comments(new_raw)
                        if cleaned:
                            cleaned_cids = [c["cid"] for c in cleaned]
                            await mark_comments_cleaned(
                                db, tracking.video_id, cleaned_cids, analysis_task.id,
                            )

                        # 6c) 更新追踪状态
                        tracking.new_comments_since_start += len(new_raw)
                        # 最新的评论 cid 作为下次的游标（评论返回顺序为最新→最旧，
                        # 但经 _fetch_new_bilibili_comments 反转后为旧→新，取最后一个）
                        if new_raw:
                            tracking.last_comment_id = new_raw[-1].get("cid", "")

                        # 更新分析任务的评论总数
                        analysis_task.total_comments_processed += len(new_raw)

                        consecutive_failures = 0
                        logger.info(
                            "追踪轮询完成: tracking_id=%s, 新增=%d (raw), 清洗后=%d, 累计=%d",
                            tracking_id, len(new_raw), len(cleaned) if cleaned else 0,
                            tracking.new_comments_since_start,
                        )
                    else:
                        # 本轮无新评论，正常
                        consecutive_failures = 0
                        logger.debug("追踪轮询: tracking_id=%s 本轮无新评论", tracking_id)

                    # 7) 条件触发增量 LLM 分析
                    time_since_last_analysis = float("inf")
                    if tracking.last_analyzed_at:
                        time_since_last_analysis = (
                            now - tracking.last_analyzed_at
                        ).total_seconds()

                    # 先做廉价的时间判断，通过后再查询 DB
                    if time_since_last_analysis >= ANALYSIS_INTERVAL_SECONDS and consecutive_analysis_failures < MAX_ANALYSIS_FAILURES:
                        unanalyzed = await _get_unanalyzed_cleaned_comments(
                            db, tracking.video_id, tracking.last_analyzed_comment_id,
                        )
                        unanalyzed_count = len(unanalyzed)

                        if unanalyzed:
                            try:
                                existing_topics = await _get_existing_topics(
                                    db, analysis_task.id,
                                )
                                comments_for_llm = [
                                    {"text": c.text or ""} for c in unanalyzed
                                ]
                                llm_result = await classify_new_comments_with_llm(
                                    comments_for_llm, existing_topics,
                                )
                                if llm_result.get("assignments"):
                                    await _apply_classification_results(
                                        db, unanalyzed, llm_result, existing_topics,
                                        analysis_task.id, tracking.video_id,
                                    )
                                    tracking.last_analyzed_comment_id = unanalyzed[-1].platform_comment_id
                                    tracking.last_analyzed_at = now
                                    consecutive_analysis_failures = 0
                                    logger.info(
                                        "追踪增量分类完成: tracking_id=%s, 已分类=%d 条",
                                        tracking_id, len(llm_result["assignments"]),
                                    )
                                else:
                                    logger.warning(
                                        "追踪增量分类: LLM 返回空结果, tracking_id=%s", tracking_id,
                                    )
                            except Exception as e:
                                consecutive_analysis_failures += 1
                                logger.error(
                                    "追踪增量分类失败 (tracking_id=%s, 连续失败=%d): %s",
                                    tracking_id, consecutive_analysis_failures, e, exc_info=True,
                                )
                                if consecutive_analysis_failures >= MAX_ANALYSIS_FAILURES:
                                    logger.error(
                                        "增量分类连续失败 %d 次，停止分析但继续轮询: tracking_id=%s",
                                        consecutive_analysis_failures, tracking_id,
                                    )
                        else:
                            logger.debug("追踪增量分类跳过: tracking_id=%s 无未分析评论", tracking_id)

                    await db.commit()

            except asyncio.CancelledError:
                logger.info("追踪轮询被取消: tracking_id=%s", tracking_id)
                break
            except Exception as e:
                consecutive_failures += 1
                logger.error(
                    "追踪轮询异常 (tracking_id=%s, 连续失败=%d): %s",
                    tracking_id, consecutive_failures, e, exc_info=True,
                )
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error("连续失败 %d 次，停止追踪: tracking_id=%s",
                                  consecutive_failures, tracking_id)
                    try:
                        async with sessionmaker() as db:
                            tracking = await db.get(TrackingTask, tracking_id)
                            if tracking:
                                tracking.status = TrackingStatus.stopped
                                tracking.stopped_at = datetime.utcnow()
                                await db.commit()
                    except Exception:
                        pass
                    break

            # 等待指定间隔后再进行下一轮轮询
            await asyncio.sleep(DEFAULT_POLL_INTERVAL)

    finally:
        # 从注册表中移除
        _active_trackings.pop(tracking_id, None)
        logger.info("追踪轮询已退出: tracking_id=%s", tracking_id)


# ──────────────────────────────────────────────
# 管理函数
# ──────────────────────────────────────────────


async def create_tracking_task(
    db: AsyncSession,
    analysis_task_id: str,
    video_id: str,
    user_id: str,
    credits_per_hour: int = 100,
) -> TrackingTask:
    """创建追踪任务记录。

    如果该 analysis_task 已有 active 追踪任务，返回已有记录（去重）。

    Raises:
        ValueError: analysis_task 不存在或 mode 非 tracking
    """
    # 去重：检查是否已有活跃追踪
    existing = await db.execute(
        select(TrackingTask).where(
            TrackingTask.analysis_task_id == analysis_task_id,
            TrackingTask.status == TrackingStatus.active,
        )
    )
    existing_task = existing.scalar_one_or_none()
    if existing_task:
        logger.info("追踪任务已存在，复用: tracking_id=%s", existing_task.id)
        return existing_task

    # 验证分析任务
    analysis_task = await db.get(AnalysisTask, analysis_task_id)
    if analysis_task is None:
        raise ValueError(f"分析任务不存在: {analysis_task_id}")
    if analysis_task.mode != AnalysisMode.tracking:
        raise ValueError(f"分析任务不是追踪模式: {analysis_task.mode}")

    # 查询最新评论的 cid 作为初始游标
    last_cid = None
    result = await db.execute(
        select(Comment.cid)
        .where(Comment.video_id == video_id)
        .order_by(Comment.create_time.desc())
        .limit(1)
    )
    row = result.one_or_none()
    if row:
        last_cid = row[0]

    now = datetime.utcnow()
    task = TrackingTask(
        id=str(uuid.uuid4()),
        analysis_task_id=analysis_task_id,
        video_id=video_id,
        user_id=user_id,
        status=TrackingStatus.active,
        poll_interval_seconds=DEFAULT_POLL_INTERVAL,
        credits_rate_per_hour=credits_per_hour,
        started_at=now,
        last_comment_id=last_cid,
        last_analyzed_comment_id=last_cid,  # 初始分析已覆盖这些评论
        last_analyzed_at=now,
    )
    db.add(task)
    await db.flush()
    logger.info(
        "追踪任务已创建: tracking_id=%s, analysis_task_id=%s, last_comment_id=%s",
        task.id, analysis_task_id, last_cid,
    )
    return task


def start_tracking(tracking_id: str) -> None:
    """启动追踪轮询（创建 asyncio.Task 并注册）。

    在 FastAPI 主事件循环中调用，追踪将作为后台任务运行。
    """
    if tracking_id in _active_trackings:
        logger.warning("追踪轮询已在运行: tracking_id=%s", tracking_id)
        return

    task = asyncio.create_task(poll_tracking_comments(tracking_id))
    _active_trackings[tracking_id] = task
    logger.info("追踪轮询已注册: tracking_id=%s, 活跃数=%d",
                 tracking_id, len(_active_trackings))


async def stop_tracking(
    tracking_id: str,
    db: AsyncSession | None = None,
) -> dict:
    """停止追踪：先更新 DB 状态，再取消 asyncio task。

    Returns:
        {stopped_at, total_new_comments, credits_consumed}
    """
    result: dict = {
        "stopped_at": datetime.utcnow().isoformat(),
        "total_new_comments": 0,
        "credits_consumed": 0.0,
    }

    async def _do_stop(sess: AsyncSession):
        tracking = await sess.get(TrackingTask, tracking_id)
        if tracking is None:
            logger.warning("stop_tracking: 追踪任务不存在: %s", tracking_id)
            return
        if tracking.status != TrackingStatus.active:
            logger.warning("stop_tracking: 追踪任务已非活跃状态: %s, status=%s",
                           tracking_id, tracking.status)
        tracking.status = TrackingStatus.stopped
        tracking.stopped_at = datetime.utcnow()
        result["total_new_comments"] = tracking.new_comments_since_start
        result["credits_consumed"] = tracking.credits_consumed
        await sess.commit()
        logger.info("追踪任务 DB 状态已更新为 stopped: tracking_id=%s", tracking_id)

    # 1) 先更新 DB — 即使 asyncio cancel 失败，下次轮询也会读到 stopped 状态
    if db:
        await _do_stop(db)
    else:
        async with get_sessionmaker()() as sess:
            await _do_stop(sess)

    # 2) 再取消后台 asyncio 任务
    if tracking_id in _active_trackings:
        task = _active_trackings.pop(tracking_id)
        task.cancel()
        logger.info("追踪轮询 asyncio task 已取消: tracking_id=%s", tracking_id)
    else:
        logger.warning("stop_tracking: tracking_id 不在活跃注册表中: %s", tracking_id)

    return result


async def get_tracking_status(
    tracking_id: str,
    db: AsyncSession,
) -> dict:
    """获取追踪任务当前状态（供 API 端点使用）。

    Returns:
        {active, new_comments, credits_remaining, credits_total, total_comments, total_topics,
         new_comments_sentiment, new_comments_topics, analyzed_comments, last_analyzed_at}
    """
    tracking = await db.get(TrackingTask, tracking_id)
    if not tracking:
        raise ValueError(f"追踪任务不存在: {tracking_id}")

    user = await db.get(User, tracking.user_id)
    credits_remaining = user.credits if user else 0

    # 查询该分析任务的评论总数和话题数
    analysis_task = await db.get(AnalysisTask, tracking.analysis_task_id)
    total_comments = analysis_task.total_comments_processed if analysis_task else 0
    total_topics = analysis_task.topic_count if analysis_task else 0

    # 查询新增评论的情感分布（仅统计追踪期间抓取的评论）
    from sqlalchemy import func, and_

    sentiment_result = await db.execute(
        select(
            Comment.sentiment,
            func.count(Comment.id).label("cnt"),
        ).where(
            and_(
                Comment.video_id == tracking.video_id,
                Comment.sentiment.isnot(None),
                Comment.fetched_at >= tracking.started_at,  # 仅追踪期间
            )
        ).group_by(Comment.sentiment)
    )
    sentiment_map = {"positive": 0, "negative": 0, "neutral": 0}
    for row in sentiment_result.all():
        if row.sentiment in sentiment_map:
            sentiment_map[row.sentiment] = row.cnt

    # 查询新增评论的话题分布（仅追踪期间）
    topic_result = await db.execute(
        select(
            Topic.name,
            func.count(Comment.id).label("cnt"),
        ).join(
            Comment, Comment.topic_id == Topic.id,
        ).where(
            and_(
                Comment.video_id == tracking.video_id,
                Comment.sentiment.isnot(None),
                Comment.fetched_at >= tracking.started_at,
                Topic.task_id == tracking.analysis_task_id,
            )
        ).group_by(Topic.name).order_by(func.count(Comment.id).desc())
    )
    new_comments_topics = []
    total_with_sentiment = sum(sentiment_map.values())
    for row in topic_result.all():
        pct = round(row.cnt / total_with_sentiment * 100, 1) if total_with_sentiment > 0 else 0
        new_comments_topics.append({
            "topic_name": row.name,
            "count": row.cnt,
            "percentage": pct,
        })

    # 已分析的评论数
    analyzed_comments = total_with_sentiment

    return {
        "active": tracking.status == TrackingStatus.active,
        "new_comments": tracking.new_comments_since_start or 0,
        "credits_remaining": credits_remaining,
        "credits_total": tracking.credits_rate_per_hour * 24,
        "total_comments": total_comments,
        "total_topics": total_topics or 0,
        "new_comments_sentiment": sentiment_map,
        "new_comments_topics": new_comments_topics,
        "analyzed_comments": analyzed_comments,
        "last_analyzed_at": tracking.last_analyzed_at.isoformat() if tracking.last_analyzed_at else None,
    }


async def get_user_active_tracking_tasks(
    db: AsyncSession,
    user_id: str,
) -> list[dict]:
    """获取用户所有追踪任务列表（供追踪页面使用）。

    Returns:
        [{tracking_id, task_id, video_title, platform, author,
          status, new_comments, credits_consumed, started_at, duration_seconds}]
    """
    result = await db.execute(
        select(
            TrackingTask.id.label("tracking_id"),
            TrackingTask.analysis_task_id.label("task_id"),
            TrackingTask.status,
            TrackingTask.new_comments_since_start,
            TrackingTask.credits_consumed,
            TrackingTask.started_at,
            TrackingTask.video_id,
            TrackingTask.poll_interval_seconds,
            Video.title.label("video_title"),
            Video.platform,
            Video.uploader_name.label("author"),
            AnalysisTask.completed_at,
            AnalysisTask.total_comments_processed.label("total_comments"),
        )
        .select_from(TrackingTask)
        .join(Video, TrackingTask.video_id == Video.id)
        .join(AnalysisTask, TrackingTask.analysis_task_id == AnalysisTask.id)
        .where(
            TrackingTask.user_id == user_id,
            TrackingTask.status == TrackingStatus.active,
        )
        .order_by(TrackingTask.started_at.desc())
    )
    items = []
    now = datetime.utcnow()
    for row in result.all():
        duration = 0
        if row.started_at:
            duration = int((now - row.started_at).total_seconds())

        # 查询该追踪任务新增评论的情感分布（仅追踪期间）
        from sqlalchemy import func, and_ as sa_and
        video_id = row.video_id
        tracking_started = row.started_at

        new_sentiment = {"positive": 0, "negative": 0, "neutral": 0}
        top_topics = []
        if video_id:
            sent_result = await db.execute(
                select(
                    Comment.sentiment,
                    func.count(Comment.id).label("cnt"),
                ).where(
                    sa_and(
                        Comment.video_id == video_id,
                        Comment.sentiment.isnot(None),
                        Comment.fetched_at >= tracking_started,
                    )
                ).group_by(Comment.sentiment)
            )
            for sr in sent_result.all():
                if sr.sentiment in new_sentiment:
                    new_sentiment[sr.sentiment] = sr.cnt

            # 查询 top 3 话题（仅追踪期间）
            topic_result = await db.execute(
                select(
                    Topic.name,
                    func.count(Comment.id).label("cnt"),
                ).join(
                    Comment, Comment.topic_id == Topic.id,
                ).where(
                    sa_and(
                        Comment.video_id == video_id,
                        Comment.sentiment.isnot(None),
                        Comment.fetched_at >= tracking_started,
                    )
                ).group_by(Topic.name).order_by(func.count(Comment.id).desc()).limit(3)
            )
            top_topics = [
                {"name": tr.name, "count": tr.cnt}
                for tr in topic_result.all()
            ]

        items.append({
            "tracking_id": row.tracking_id,
            "task_id": row.task_id,
            "video_title": row.video_title or "",
            "platform": row.platform.value if hasattr(row.platform, 'value') else str(row.platform),
            "author": row.author or "",
            "status": row.status.value if hasattr(row.status, 'value') else str(row.status),
            "new_comments": row.new_comments_since_start or 0,
            "credits_consumed": round(row.credits_consumed or 0, 1),
            "total_comments": row.total_comments or 0,
            "credits_remaining": 0,  # 由调用方补充
            "duration_seconds": duration,
            "analysis_finished_at": row.completed_at.isoformat() if row.completed_at else "",
            "recent_logs": [],
            "new_sentiment": new_sentiment,
            "top_topics": top_topics,
        })
    return items


async def has_active_tracking(db: AsyncSession, user_id: str) -> bool:
    """检查用户是否有活跃的追踪任务。"""
    result = await db.execute(
        select(TrackingTask.id).where(
            TrackingTask.user_id == user_id,
            TrackingTask.status == TrackingStatus.active,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


# ──────────────────────────────────────────────
# 生命周期管理
# ──────────────────────────────────────────────


async def resume_all_active_trackings() -> int:
    """服务器启动时恢复所有 status=active 的追踪任务。

    只有 last_poll_at 在 5 分钟内的任务才会被恢复。
    超过 5 分钟的视为上次服务器异常关闭的遗留，直接标记为 stopped。

    Returns:
        int: 恢复的任务数
    """
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    async with get_sessionmaker()() as db:
        from sqlalchemy import update as sql_update
        result = await db.execute(
            select(TrackingTask).where(
                TrackingTask.status == TrackingStatus.active,
            )
        )
        all_tasks = result.scalars().all()

        resumed = 0
        for task in all_tasks:
            # 跳过已经在内存中的
            if task.id in _active_trackings:
                continue

            # 上次轮询超过 5 分钟 → 视为过期遗留，标记为 stopped
            if task.last_poll_at and task.last_poll_at < cutoff:
                logger.info("追踪任务过期，标记为 stopped: tracking_id=%s, last_poll_at=%s",
                             task.id, task.last_poll_at)
                task.status = TrackingStatus.stopped
                task.stopped_at = datetime.utcnow()
                continue
            elif not task.last_poll_at:
                # 从未轮询过 — 也视为遗留
                started_cutoff = datetime.utcnow() - timedelta(minutes=5)
                if task.started_at < started_cutoff:
                    logger.info("追踪任务启动后从未轮询，标记为 stopped: tracking_id=%s", task.id)
                    task.status = TrackingStatus.stopped
                    task.stopped_at = datetime.utcnow()
                    continue

            start_tracking(task.id)
            resumed += 1

        if all_tasks:
            await db.commit()

    if resumed:
        logger.info("已恢复 %d 个活跃追踪任务", resumed)
    return resumed


async def shutdown_all_trackings():
    """服务器关闭时取消所有追踪轮询任务，并将 DB 状态改为 stopped。

    如果不更新 DB，下次启动时 resume_all_active_trackings 会错误地
    恢复这些已关闭服务器的遗留任务。
    """
    count = len(_active_trackings)
    for tracking_id, task in list(_active_trackings.items()):
        task.cancel()
        logger.info("关闭时取消追踪: tracking_id=%s", tracking_id)
    _active_trackings.clear()

    # 将 DB 中所有 active 追踪任务标记为 stopped
    # 防止服务器崩溃/重启后错误地恢复旧任务
    try:
        async with get_sessionmaker()() as db:
            from sqlalchemy import update as sql_update
            now = datetime.utcnow()
            result = await db.execute(
                sql_update(TrackingTask)
                .where(TrackingTask.status == TrackingStatus.active)
                .values(status=TrackingStatus.stopped, stopped_at=now)
            )
            await db.commit()
            if result.rowcount:
                logger.info("已将 %d 个活跃追踪任务标记为 stopped", result.rowcount)
    except Exception as e:
        logger.error("关闭时更新追踪任务 DB 状态失败: %s", e)

    logger.info("所有追踪任务已清理 (取消 %d 个)", count)
