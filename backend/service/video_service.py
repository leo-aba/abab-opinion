"""视频搜索 Service — URL 解析、平台 API 调用、数据库读写
搜索策略：每次都实时调用平台 API 获取最新数据，然后根据 DB 有无记录决定 INSERT 或 UPDATE。
"""

import re
import uuid
import logging
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.video import Video, Platform

logger = logging.getLogger("video_service")

# Bilibili API 请求头（模拟浏览器访问）
BILIBILI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}

# B站 BV 号正则：BV + 10位字母数字
_BV_PATTERN = re.compile(r"BV[0-9A-Za-z]{10}")

# 抖音视频 ID 正则：/video/ 后跟纯数字
_DOUYIN_PATTERN = re.compile(r"douyin\.com/video/(\d+)")


# ──────────────────────────────────────────────
# URL 解析
# ──────────────────────────────────────────────

def parse_video_url(url: str) -> tuple[str, str]:
    """解析视频 URL，返回 (platform, platform_video_id)。

    支持的格式:
      - Bilibili: https://www.bilibili.com/video/BVxxx/  或纯 BV 号
      - Douyin:   https://www.douyin.com/video/123456.../

    Raises:
        ValueError: 无法从 URL 中识别平台或视频 ID
    """
    url = url.strip()

    # 1) 尝试匹配 Bilibili BV 号
    bv_match = _BV_PATTERN.search(url)
    if bv_match:
        return Platform.bilibili.value, bv_match.group(0)

    # 2) 尝试匹配抖音视频 ID
    douyin_match = _DOUYIN_PATTERN.search(url)
    if douyin_match:
        return Platform.douyin.value, douyin_match.group(1)

    raise ValueError("无法识别的视频链接，目前支持 Bilibili（bilibili.com）和抖音（douyin.com）")


# ──────────────────────────────────────────────
# 数据库查询
# ──────────────────────────────────────────────

async def find_video_by_platform_id(
    db: AsyncSession, platform: str, platform_video_id: str
) -> Video | None:
    """根据平台和平台视频 ID 查询已入库的视频"""
    result = await db.execute(
        select(Video).where(
            Video.platform == platform,
            Video.platform_video_id == platform_video_id,
        )
    )
    return result.scalar_one_or_none()


# ──────────────────────────────────────────────
# Bilibili API 抓取
# ──────────────────────────────────────────────

async def fetch_bilibili_video_info(bvid: str) -> dict | None:
    """调用 Bilibili API 获取视频元信息，返回与 videos 表对齐的 dict（不含 id）。

    参考: test/bilibili/video_info_crawler_test.py
    """
    api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(api_url, headers=BILIBILI_HEADERS)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error("Bilibili API 请求失败: %s", e)
        raise RuntimeError(f"请求 Bilibili API 失败: {e}") from e

    if data.get("code") != 0:
        msg = data.get("message", "未知错误")
        logger.warning("Bilibili API 返回错误: code=%s, message=%s", data.get("code"), msg)
        raise RuntimeError(f"Bilibili API 错误: {msg}")

    video = data["data"]
    owner = video.get("owner", {})
    stat = video.get("stat", {})

    publish_time = None
    pubdate = video.get("pubdate")
    if pubdate:
        publish_time = datetime.fromtimestamp(pubdate).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "platform": Platform.bilibili.value,
        "platform_video_id": bvid,
        "title": video.get("title", ""),
        "description": video.get("desc") or None,
        "cover_url": video.get("pic") or None,
        "uploader_name": owner.get("name") or None,
        "uploader_id": str(owner["mid"]) if owner.get("mid") else None,
        "url": f"https://www.bilibili.com/video/{bvid}/",
        "publish_time": publish_time,
        "duration_seconds": video.get("duration"),
        "comment_count": stat.get("reply", 0),
        "view_count": stat.get("view"),
        "like_count": stat.get("like"),
        "analysis_status": "pending",
    }


# ──────────────────────────────────────────────
# 数据库 插入 / 更新
# ──────────────────────────────────────────────

async def upsert_video(db: AsyncSession, info: dict) -> Video:
    """根据 platform + platform_video_id 判断：
    - 已有记录 → 更新字段（评论数、播放量等实时数据）
    - 无记录   → 新增一条
    返回对应的 Video 对象。
    """
    existing = await find_video_by_platform_id(db, info["platform"], info["platform_video_id"])

    if existing:
        # 更新实时变化的字段
        existing.title = info["title"]
        existing.description = info["description"]
        existing.cover_url = info["cover_url"]
        existing.uploader_name = info["uploader_name"]
        existing.uploader_id = info["uploader_id"]
        existing.url = info["url"]
        existing.publish_time = info["publish_time"]
        existing.duration_seconds = info["duration_seconds"]
        existing.comment_count = info["comment_count"]
        existing.view_count = info["view_count"]
        existing.like_count = info["like_count"]
        # updated_at 由 SQLAlchemy onupdate 自动设置
        logger.info("已更新: platform=%s, id=%s, title=%s",
                     info["platform"], info["platform_video_id"], info["title"])
        await db.flush()
        return existing
    else:
        # 新记录：需要生成 id
        info["id"] = str(uuid.uuid4())
        video = Video(**info)
        db.add(video)
        logger.info("已入库: platform=%s, id=%s, title=%s",
                     info["platform"], info["platform_video_id"], info["title"])
        await db.flush()
        return video


# ──────────────────────────────────────────────
# 核心搜索逻辑
# ──────────────────────────────────────────────

async def search_video_by_url(query: str, db: AsyncSession) -> list[dict]:
    """根据 URL 搜索视频：始终实时调用平台 API，再 upsert 到数据库。

    返回前端期望的格式:
        [{video_id, title, cover_url, uploader, comment_count}]

    Raises:
        ValueError: URL 无法识别
        RuntimeError: 平台 API 调用失败
    """
    # 1) 解析 URL → platform + video_id
    platform, video_id = parse_video_url(query)

    # 2) 实时调用平台 API 获取最新数据
    logger.info("实时抓取: platform=%s, id=%s", platform, video_id)

    if platform == Platform.bilibili.value:
        info = await fetch_bilibili_video_info(video_id)
    elif platform == Platform.douyin.value:
        # 抖音 API 需要 cookie/签名鉴权，暂不实现实时抓取
        raise RuntimeError(
            "抖音视频搜索暂不支持实时查询。"
            "请先在系统中录入该视频，或联系管理员。"
        )
    else:
        raise RuntimeError(f"不支持的平台: {platform}")

    if info is None:
        raise RuntimeError("获取视频信息失败，请检查链接是否正确")

    # 3) upsert 到数据库（已有则更新，没有则插入）
    video = await upsert_video(db, info)

    return [_video_to_search_item(video)]


# ──────────────────────────────────────────────
# 格式化
# ──────────────────────────────────────────────

def _video_to_search_item(video: Video) -> dict:
    """将 Video ORM 对象转为前端期望的搜索条目格式"""
    return {
        "video_id": video.id,
        "title": video.title,
        "cover_url": video.cover_url,
        "uploader": video.uploader_name,  # 前端 create-analysis.html 使用 v.uploader
        "comment_count": video.comment_count,
    }
