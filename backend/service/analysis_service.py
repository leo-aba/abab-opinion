"""分析任务 Service — 创建、查询分析任务"""

import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.analysis_task import (
    AnalysisTask, AnalysisMode, AnalysisStatus, TimeRange, LanguageFilter,
)
from backend.service.video_service import (
    parse_video_url, find_video_by_platform_id, upsert_video, fetch_bilibili_video_info,
)

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


async def create_analysis_task(
    db: AsyncSession,
    user_id: str,
    mode: str,
    video_url: str,
    comment_count: int,
    time_range: str,
    language: str,
) -> AnalysisTask:
    """创建分析任务。

    步骤:
    1. 解析 video_url → (platform, platform_video_id)
    2. 查找或创建 Video 记录（复用 video_service）
    3. 创建 AnalysisTask 记录，status='queued'

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
        else:
            raise RuntimeError(
                "抖音视频搜索暂不支持实时查询。请先在系统中录入该视频，或联系管理员。"
            )

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

    logger.info(
        "分析任务已创建: task_id=%s user=%s video=%s platform=%s mode=%s",
        task.id, user_id, video.id, platform, mode,
    )
    return task
