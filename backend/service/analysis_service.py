"""分析任务 Service — 创建、查询分析任务"""

import json
import os
import uuid
import logging
from pathlib import Path
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_sessionmaker
from backend.models.video import Video
from backend.models.analysis_task import (
    AnalysisTask, AnalysisMode, AnalysisStatus, TimeRange, LanguageFilter,
)
from backend.service.video_service import (
    parse_video_url, find_video_by_platform_id, upsert_video,
    fetch_bilibili_video_info, fetch_bilibili_comments,
    fetch_douyin_video_info, fetch_douyin_comments,
)
from backend.service.comment_service import batch_upsert_comments, delete_comments_by_video
from backend.service.comment_cleaner import clean_comments

logger = logging.getLogger("analysis_service")

# 前端中文时间范围文案 → DB 枚举值
_TIME_RANGE_MAP = {
    "最近7天": TimeRange.d7,
    "最近30天": TimeRange.d30,
    "全部": TimeRange.all,
    # count-based 模式默认不限时间
    "最近100条": TimeRange.all,
    "最近200条": TimeRange.all,
    "最近500条": TimeRange.all,
}


def _map_time_range(frontend_value: str) -> TimeRange:
    """将前端时间范围文案映射为 DB 枚举值"""
    return _TIME_RANGE_MAP.get(frontend_value, TimeRange.all)


async def run_crawl_task(
    task_id: str,
    video_id: str,
    platform: str,
    platform_video_id: str,
    comment_limit: int,
) -> None:
    """后台爬取任务：在独立 DB session 中执行，更新任务状态。

    流程:
    1. 爬取评论 → 保存到本地 JSON
    2. 清洗评论（过滤无意义内容）
    3. 删除本地临时文件
    4. 删除该视频旧评论（DB）
    5. 清洗后的评论写入 DB

    状态流转: queued → collecting → cleaning → completed / failed
    """
    logger.info("后台爬取任务启动: task_id=%s, video_id=%s", task_id, video_id)

    # 本地临时文件目录
    _DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    async def _update_status(db: AsyncSession | None, status: AnalysisStatus, **kwargs):
        """更新任务状态，若 db 为 None 则创建新 session。"""
        if db is not None:
            task = await db.get(AnalysisTask, task_id)
            if task is None:
                logger.error("任务不存在: %s", task_id)
                return
            task.status = status
            for k, v in kwargs.items():
                setattr(task, k, v)
            await db.commit()
        else:
            async with get_sessionmaker()() as sess:
                task = await sess.get(AnalysisTask, task_id)
                if task is None:
                    logger.error("任务不存在: %s", task_id)
                    return
                task.status = status
                for k, v in kwargs.items():
                    setattr(task, k, v)
                await sess.commit()

    logger.info("run_crawl_task invoked: task_id=%s, video_id=%s, platform=%r, platform_video_id=%s, comment_limit=%s",
                 task_id, video_id, platform, platform_video_id, comment_limit)

    raw_file_path = None

    try:
        # ── 1) 获取视频元数据 ──
        async with get_sessionmaker()() as db:
            video = await db.get(Video, video_id)
            if video is None:
                raise ValueError(f"视频不存在: {video_id}")
            extras = video.extras if video.extras else {}

        # ── 2) 状态 → collecting ──
        async with get_sessionmaker()() as db:
            await _update_status(db, AnalysisStatus.collecting, progress_pct=5)

        # ── 3) 爬取评论（根据平台分发）──
        crawl_db = await get_sessionmaker()().__aenter__()
        try:
            async def _crawl_progress(current: int, target: int):
                """每页抓取后的进度回调，10% → 80% 映射到爬取阶段"""
                if target > 0:
                    pct = 10 + int((current / target) * 70)
                    pct = min(max(pct, 10), 80)
                else:
                    pct = 10
                await _update_status(
                    crawl_db, AnalysisStatus.collecting,
                    progress_pct=pct,
                    total_comments_processed=current,
                )

            if platform == "bilibili":
                aid = extras.get("aid")
                if not aid:
                    raise ValueError(f"缺少 aid 字段，无法爬取评论 (video_id={video_id})")
                logger.info("开始爬取 B站评论: aid=%s, max_count=%s", aid, comment_limit)
                raw_comments = await fetch_bilibili_comments(
                    aid, comment_limit,
                    progress_callback=_crawl_progress,
                )
            elif platform == "douyin":
                logger.info("开始爬取抖音评论: video_id=%s, max_count=%s", platform_video_id, comment_limit)
                raw_comments = await fetch_douyin_comments(
                    platform_video_id, comment_limit,
                    progress_callback=_crawl_progress,
                )
            else:
                raise ValueError(f"不支持的平台: {platform}")
        finally:
            await crawl_db.__aexit__(None, None, None)

        logger.info("%s评论爬取完成: 共 %s 条", platform, len(raw_comments))

        # ── 4) 保存原始评论到本地 JSON ──
        raw_file_path = _DATA_DIR / f"raw_comments_{task_id}.json"
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(raw_comments, f, ensure_ascii=False, default=str)
        logger.info("原始评论已保存到本地: %s (%d 条)", raw_file_path, len(raw_comments))

        # ── 5) 状态 → cleaning，清洗评论 ──
        async with get_sessionmaker()() as db:
            await _update_status(db, AnalysisStatus.cleaning, progress_pct=85)

        cleaned_comments, clean_stats = clean_comments(raw_comments)
        logger.info(
            "评论清洗完成: 原始=%d, 保留=%d, 去除=%d",
            clean_stats["total"], clean_stats["kept"], clean_stats["removed"],
        )

        # ── 6) 删除本地临时文件 ──
        if raw_file_path and raw_file_path.exists():
            raw_file_path.unlink()
            logger.info("本地临时文件已删除: %s", raw_file_path)
            raw_file_path = None

        # ── 7) 删除该视频旧评论 + 写入清洗后评论 ──
        async with get_sessionmaker()() as db:
            # 7a) 删除旧评论
            deleted_count = await delete_comments_by_video(db, video_id)
            logger.info("已删除视频 %s 的旧评论 %d 条", video_id, deleted_count)

            # 7b) 写入清洗后的评论
            logger.info("DEBUG: platform value before batch_upsert_comments = %r", platform)
            inserted = await batch_upsert_comments(
                db, video_id, platform, cleaned_comments, task_id,
            )

            # 7c) 完成 → 更新状态（包含清洗统计）
            await _update_status(
                db, AnalysisStatus.completed,
                progress_pct=100,
                total_comments_processed=inserted,
                error_message=json.dumps(clean_stats, ensure_ascii=False),
            )

        logger.info(
            "后台爬取任务完成: task_id=%s, 清洗后评论=%d (原始=%d)",
            task_id, inserted, len(raw_comments),
        )

    except Exception as e:
        logger.error("后台爬取任务失败: task_id=%s, error=%s", task_id, e)
        # 清理本地临时文件
        if raw_file_path and raw_file_path.exists():
            try:
                raw_file_path.unlink()
                logger.info("异常时清理本地临时文件: %s", raw_file_path)
            except OSError:
                pass
        try:
            async with get_sessionmaker()() as db:
                await _update_status(
                    db, AnalysisStatus.failed,
                    error_message=str(e),
                    progress_pct=0,
                )
        except Exception as db_e:
            logger.error("更新失败状态时出错: %s", db_e)


async def create_analysis_task(
    db: AsyncSession,
    user_id: str,
    mode: str,
    video_url: str,
    comment_count: int,
    time_range: str,
    language: str,
    background_tasks: BackgroundTasks | None = None,
) -> AnalysisTask:
    """创建分析任务。

    步骤:
    1. 解析 video_url → (platform, platform_video_id)
    2. 查找或创建 Video 记录（复用 video_service）
    3. 创建 AnalysisTask 记录，status='queued'
    4. 注册后台爬取任务（如果提供 background_tasks）

    Raises:
        ValueError: URL 无法识别
        RuntimeError: 平台 API 调用失败（如 Bilibili 接口异常）
    """
    # 1) 解析 URL
    platform, platform_video_id = parse_video_url(video_url)

    # 2) 查找或创建 Video
    video = await find_video_by_platform_id(db, platform, platform_video_id)

    if video is None:
        logger.info("视频未入库，实时抓取: platform=%s id=%s", platform, platform_video_id)
        if platform == "bilibili":
            info = await fetch_bilibili_video_info(platform_video_id)
            if info is None:
                raise RuntimeError("获取视频信息失败，请检查链接是否正确")
            video = await upsert_video(db, info)
        elif platform == "douyin":
            info = await fetch_douyin_video_info(platform_video_id)
            if info is None:
                raise RuntimeError("获取抖音视频信息失败，请检查链接是否正确")
            video = await upsert_video(db, info)
        else:
            raise RuntimeError(f"不支持的平台: {platform}")

    # 3) 创建 AnalysisTask
    lang = language if language in ("zh", "en", "all") else "all"
    task = AnalysisTask(
        id=str(uuid.uuid4()),
        user_id=user_id,
        video_id=video.id,
        platform=platform,
        mode=AnalysisMode(mode),
        comment_limit=comment_count,
        time_range=_map_time_range(time_range),
        language_filter=LanguageFilter(lang),
        status=AnalysisStatus.queued,
    )
    db.add(task)
    await db.flush()

    # 4) 注册后台爬取任务
    if background_tasks is not None:
        background_tasks.add_task(
            run_crawl_task,
            task_id=task.id,
            video_id=video.id,
            platform=platform,
            platform_video_id=platform_video_id,
            comment_limit=comment_count,
        )

    # 提前提交事务，确保后台任务能在独立 session 中查到该记录
    await db.commit()

    logger.info(
        "分析任务已创建: task_id=%s user=%s video=%s platform=%s mode=%s",
        task.id, user_id, video.id, platform, mode,
    )
    return task
