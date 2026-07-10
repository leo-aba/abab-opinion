"""视频搜索 Service — URL 解析、平台 API 调用、数据库读写
搜索策略：每次都实时调用平台 API 获取最新数据，然后根据 DB 有无记录决定 INSERT 或 UPDATE。
"""

import asyncio
import re
import uuid
import logging
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.video import Video, Platform
from backend.models.analysis_task import AnalysisTask

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_COVERS_DIR = PROJECT_ROOT / "data" / "covers"

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

# 抖音视频 ID 正则：/video/ 后跟纯数字，或 /jingxuan 的 modal_id 参数
_DOUYIN_PATTERN = re.compile(r"douyin\.com/video/(\d+)")
_DOUYIN_MODAL_PATTERN = re.compile(r"douyin\.com/jingxuan.*[?&]modal_id=(\d+)")


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

    # 2) 尝试匹配抖音视频 ID（/video/ 或 /jingxuan?modal_id=）
    douyin_match = _DOUYIN_PATTERN.search(url)
    if not douyin_match:
        douyin_match = _DOUYIN_MODAL_PATTERN.search(url)
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
# 封面下载
# ──────────────────────────────────────────────


async def _download_cover(cover_url: str, referer: str = "https://www.bilibili.com/") -> str | None:
    """下载视频封面到本地 data/covers/，返回本地访问路径。

    下载失败（超时、HTTP 错误、文件过小）时返回 None，
    调用方应回退到远程 URL。
    """
    _COVERS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = _COVERS_DIR / filename
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(cover_url, headers={"Referer": referer})
            if resp.status_code == 200 and len(resp.content) > 1024:
                filepath.write_bytes(resp.content)
                logger.info("封面已下载: %s → %s", cover_url[:60], filename)
                return f"/covers/{filename}"
    except Exception as e:
        logger.warning("封面下载失败 (%s): %s", cover_url[:60], e)
    return None


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

    cover_url = video.get("pic") or None
    local_cover = await _download_cover(cover_url) if cover_url else None

    return {
        "platform": Platform.bilibili.value,
        "platform_video_id": bvid,
        "title": video.get("title", ""),
        "description": video.get("desc") or None,
        "cover_url": local_cover or cover_url,
        "uploader_name": owner.get("name") or None,
        "uploader_id": str(owner["mid"]) if owner.get("mid") else None,
        "url": f"https://www.bilibili.com/video/{bvid}/",
        "publish_time": publish_time,
        "duration_seconds": video.get("duration"),
        "comment_count": stat.get("reply", 0),
        "view_count": stat.get("view"),
        "like_count": stat.get("like"),
        "extras": {"aid": video.get("aid")},
        "analysis_status": "pending",
    }


# ──────────────────────────────────────────────
# B站评论爬取（异步 httpx 版）
# ──────────────────────────────────────────────

async def fetch_bilibili_comment_page(
    aid: int, cursor: int = 0, mode: int = 3
) -> tuple[list[dict] | None, int | None, bool]:
    """抓取一页 B站一级评论（异步 httpx 版）。

    API: https://api.bilibili.com/x/v2/reply/main
    参数: oid=aid, type=1(视频), mode=2(时间)/3(热度), next=cursor

    Returns:
        (replies, next_cursor, is_end)
        replies 为 None 表示接口异常。
    """
    params = {
        "oid": aid,
        "type": 1,
        "mode": mode,
        "next": cursor,
    }
    url = "https://api.bilibili.com/x/v2/reply/main"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=BILIBILI_HEADERS, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error("Bilibili 评论 API 请求失败: %s", e)
        raise RuntimeError(f"请求 Bilibili 评论 API 失败: {e}") from e

    if data.get("code") != 0:
        msg = data.get("message", "未知错误")
        logger.warning("Bilibili 评论 API 返回错误: code=%s, message=%s", data.get("code"), msg)
        raise RuntimeError(f"Bilibili 评论 API 错误: {msg}")

    cursor_data = data.get("data", {}).get("cursor", {})
    replies = data.get("data", {}).get("replies")
    next_cursor = cursor_data.get("next")
    is_end = cursor_data.get("is_end", True)
    return replies, next_cursor, is_end


def _extract_bilibili_comment_info(c: dict) -> dict:
    """提取单条 B站评论的字段，与 test/bilibili_crawler.py extract_comment_info 一致"""
    ctime = c.get("ctime", 0)
    return {
        "cid": str(c.get("rpid", "")),
        "text": c.get("content", {}).get("message", ""),
        "create_time": datetime.fromtimestamp(ctime) if ctime else None,
        "digg_count": c.get("like", 0),
        "reply_comment_total": c.get("rcount", 0),
        "user": {
            "uid": str(c.get("member", {}).get("mid", "")),
            "nickname": c.get("member", {}).get("uname", ""),
            "avatar": c.get("member", {}).get("avatar", ""),
        },
    }


async def fetch_bilibili_comments(
    aid: int, max_count: int = 500,
    progress_callback=None,
) -> list[dict]:
    """抓取 B站评论，直到达到 max_count 或没有更多。

    Args:
        aid: 视频 aid（从 video.extras 获取）
        max_count: 最多抓取条数，0 表示全部抓取
        progress_callback: 可选异步回调，每页抓取后调用
            progress_callback(current_count, target_count)

    Returns:
        list[dict]: 评论列表，每项格式同 _extract_bilibili_comment_info
    """
    all_comments: list[dict] = []
    cursor = 0
    page = 0
    is_end = False
    sleep_sec = 1.2

    # 估算总页数：假设每页约 20 条，用于进度估算
    estimated_per_page = 20

    while not is_end:
        if max_count > 0 and len(all_comments) >= max_count:
            break

        page += 1
        logger.debug("抓取评论第 %s 页 (cursor=%s)...", page, cursor)

        replies, next_cursor, is_end = await fetch_bilibili_comment_page(aid, cursor)

        if replies is None:
            break
        if not replies:
            break

        for c in replies:
            all_comments.append(_extract_bilibili_comment_info(c))
            if max_count > 0 and len(all_comments) >= max_count:
                break

        logger.info("评论抓取进度: 第 %s 页, 累计 %s 条", page, len(all_comments))

        # 每页抓取后回调（用于前端进度展示）
        if progress_callback:
            target = max_count if max_count > 0 else (page * estimated_per_page * 2)
            await progress_callback(len(all_comments), target)

        cursor = next_cursor if next_cursor is not None else cursor

        # 防限流休眠
        if not is_end and (max_count == 0 or len(all_comments) < max_count):
            await asyncio.sleep(sleep_sec)

    logger.info("B站评论抓取完成: aid=%s, 共 %s 条", aid, len(all_comments))
    return all_comments


# ──────────────────────────────────────────────
# 抖音 API 抓取（Selenium + JS fetch，需要已登录的浏览器 Cookie）
# ──────────────────────────────────────────────

_DOUYIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.douyin.com/",
}


def _create_douyin_driver():
    """创建 Selenium Chrome Driver（含反检测配置，headless 模式）"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument(f'--user-agent={_DOUYIN_HEADERS["User-Agent"]}')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    driver.set_script_timeout(15)
    return driver


def _douyin_init_session(driver) -> None:
    """初始化抖音浏览器会话：访问首页获取 Cookie"""
    import time
    driver.get("https://www.douyin.com/")
    time.sleep(1.5)


def _douyin_js_fetch(driver, url: str) -> dict:
    """通过 JS fetch 从浏览器内部调用抖音 API，返回 JSON dict"""
    import json as _json
    js = """
    var url = arguments[0];
    var callback = arguments[arguments.length - 1];
    fetch(url, {
        credentials: "include",
        headers: {"Accept": "application/json"}
    }).then(function(r) { return r.json(); }).then(function(d) {
        callback(JSON.stringify(d));
    }).catch(function(e) {
        callback(JSON.stringify({_error: e.message}));
    });
    """
    raw = driver.execute_async_script(js, url)
    return _json.loads(raw)


def _extract_douyin_comment_info(c: dict) -> dict:
    """提取单条抖音评论字段，与 B站 _extract_bilibili_comment_info 格式对齐"""
    ctime = c.get("create_time", 0)
    return {
        "cid": str(c.get("cid", "")),
        "text": c.get("text", ""),
        "create_time": datetime.fromtimestamp(ctime) if ctime else None,
        "digg_count": c.get("digg_count", 0),
        "reply_comment_total": c.get("reply_comment_total", 0),
        "user": {
            "uid": str(c.get("user", {}).get("uid", "")),
            "nickname": c.get("user", {}).get("nickname", ""),
            "avatar": c.get("user", {}).get("avatar_thumb", {}).get("url_list", [""])[0]
            if c.get("user", {}).get("avatar_thumb") else None,
        },
    }


async def fetch_douyin_video_info(video_id: str) -> dict | None:
    """通过 Selenium 获取抖音视频元信息，返回与 videos 表对齐的 dict。

    使用 JS fetch 调用抖音 aweme/detail API。
    """
    import time
    api_url = (
        f"https://www.douyin.com/aweme/v1/web/aweme/detail/"
        f"?aweme_id={video_id}&device_platform=webapp"
    )
    driver = _create_douyin_driver()
    try:
        _douyin_init_session(driver)

        # 访问视频页面让浏览器建立 Referer 上下文
        driver.get(f"https://www.douyin.com/video/{video_id}")
        time.sleep(1.5)

        data = await asyncio.to_thread(_douyin_js_fetch, driver, api_url)

        if "_error" in data:
            raise RuntimeError(f"抖音 API 请求失败: {data['_error']}")

        aweme = data.get("aweme_detail")
        if not aweme:
            raise RuntimeError("抖音 API 未返回视频数据")

        author = aweme.get("author", {})
        stat = aweme.get("statistics", {})

        publish_time = None
        create_time_ts = aweme.get("create_time")
        if create_time_ts:
            publish_time = datetime.fromtimestamp(create_time_ts).strftime("%Y-%m-%d %H:%M:%S")

        cover_url = (
            aweme.get("video", {}).get("cover", {}).get("url_list", [""])[0]
            or aweme.get("video", {}).get("origin_cover", {}).get("url_list", [""])[0]
            or None
        )
        local_cover = await _download_cover(cover_url, referer="https://www.douyin.com/") if cover_url else None

        return {
            "platform": Platform.douyin.value,
            "platform_video_id": video_id,
            "title": aweme.get("desc") or aweme.get("preview_title") or "",
            "description": aweme.get("desc") or None,
            "cover_url": local_cover or cover_url,
            "uploader_name": author.get("nickname") or None,
            "uploader_id": str(author.get("uid", "")) if author.get("uid") else None,
            "url": f"https://www.douyin.com/video/{video_id}/",
            "publish_time": publish_time,
            "duration_seconds": aweme.get("video", {}).get("duration"),
            "comment_count": stat.get("comment_count", 0),
            "view_count": stat.get("play_count"),
            "like_count": stat.get("digg_count"),
            "extras": {"aweme_id": video_id},
            "analysis_status": "pending",
        }
    finally:
        driver.quit()


async def fetch_douyin_comments(
    video_id: str,
    max_count: int = 500,
    progress_callback=None,
) -> list[dict]:
    """抓取抖音评论，直到达到 max_count 或没有更多。

    通过 Selenium + JS fetch 调用抖音评论 API。
    返回格式与 fetch_bilibili_comments 一致。

    Args:
        video_id: 抖音视频 ID（19位数字）
        max_count: 最多抓取条数，0 表示全部抓取
        progress_callback: 可选异步回调，每页抓取后调用
    """
    import time
    import json as _json

    all_comments: list[dict] = []
    cursor = 0
    page = 0
    has_more = True
    sleep_sec = 1.5

    driver = _create_douyin_driver()
    try:
        _douyin_init_session(driver)

        # 访问视频页面建立上下文
        driver.get(f"https://www.douyin.com/video/{video_id}")
        await asyncio.sleep(3)

        while has_more:
            if max_count > 0 and len(all_comments) >= max_count:
                break

            page += 1
            logger.debug("抖音评论抓取第 %s 页 (cursor=%s)...", page, cursor)

            api_url = (
                f"https://www.douyin.com/aweme/v1/web/comment/list/"
                f"?aweme_id={video_id}&cursor={cursor}&count=20&device_platform=webapp"
            )
            data = await asyncio.to_thread(_douyin_js_fetch, driver, api_url)

            if "_error" in data:
                logger.error("抖音评论 API 错误: %s", data["_error"])
                break

            comments = data.get("comments")
            if not comments:
                logger.info("抖音评论: 第 %s 页无数据，停止", page)
                break

            for c in comments:
                all_comments.append(_extract_douyin_comment_info(c))
                if max_count > 0 and len(all_comments) >= max_count:
                    break

            logger.info("抖音评论抓取进度: 第 %s 页, 累计 %s 条", page, len(all_comments))

            if progress_callback:
                target = max_count if max_count > 0 else page * 20 * 2
                await progress_callback(len(all_comments), target)

            has_more = data.get("has_more", False)
            cursor = data.get("cursor", cursor)

            if has_more and (max_count == 0 or len(all_comments) < max_count):
                await asyncio.sleep(sleep_sec)

    finally:
        driver.quit()

    logger.info("抖音评论抓取完成: video_id=%s, 共 %s 条", video_id, len(all_comments))
    return all_comments


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
        existing.extras = info.get("extras")
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
    """根据 URL 搜索视频：优先查数据库缓存，无记录时实时调用平台 API。

    返回前端期望的格式:
        [{video_id, title, cover_url, uploader, comment_count}]

    Raises:
        ValueError: URL 无法识别
        RuntimeError: 平台 API 调用失败
    """
    # 1) 解析 URL → platform + video_id
    platform, video_id = parse_video_url(query)

    # 2) 优先查数据库 — 已有记录则直接返回（避免慢速 API 调用）
    existing = await find_video_by_platform_id(db, platform, video_id)
    if existing:
        logger.info("数据库命中: platform=%s, id=%s, title=%s", platform, video_id, existing.title[:40])
        return [_video_to_search_item(existing)]

    # 3) 数据库无记录 → 实时调用平台 API
    logger.info("实时抓取: platform=%s, id=%s", platform, video_id)

    if platform == Platform.bilibili.value:
        info = await fetch_bilibili_video_info(video_id)
    elif platform == Platform.douyin.value:
        info = await fetch_douyin_video_info(video_id)
    else:
        raise RuntimeError(f"不支持的平台: {platform}")

    if info is None:
        raise RuntimeError("获取视频信息失败，请检查链接是否正确")

    # 4) upsert 到数据库
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


# ──────────────────────────────────────────────
# 视频列表（视频管理页）
# ──────────────────────────────────────────────


async def get_video_list(
    db: AsyncSession,
    user_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """查询当前用户关联的视频列表（去重，按最近分析时间倒序）。

    Video 表无 user_id，通过 AnalysisTask 关联用户，同一个视频
    只返回一次（取最新的分析时间）。

    Returns:
        {total, total_pages, page, page_size, items: [{video_id, title,
          cover_url, platform, author, comment_count, status,
          last_analysis_date, publish_date, new_comments_since_tracking}]}
    """
    import math

    # 基础查询 — 去重 + 取最新分析时间
    cols = [
        Video.id.label("video_id"),
        Video.title,
        Video.cover_url,
        Video.url,
        Video.platform_video_id,
        Video.platform,
        Video.uploader_name.label("author"),
        Video.comment_count,
        Video.analysis_status.label("status"),
        Video.last_analysis_at,
        Video.publish_time,
    ]

    # 子查询：每个视频取最新分析时间
    latest_sub = (
        select(
            AnalysisTask.video_id,
            func.max(AnalysisTask.created_at).label("latest_analysis"),
        )
        .where(AnalysisTask.user_id == user_id)
        .group_by(AnalysisTask.video_id)
        .subquery()
    )

    base_stmt = (
        select(*cols, latest_sub.c.latest_analysis.label("last_analysis_date"))
        .select_from(Video)
        .join(latest_sub, Video.id == latest_sub.c.video_id)
    )

    # 统计总数
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = await db.scalar(count_stmt) or 0

    # 排序 + 分页
    base_stmt = base_stmt.order_by(latest_sub.c.latest_analysis.desc())
    base_stmt = base_stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(base_stmt)
    rows = result.all()

    # 批量查询每行视频对应的最新 task_id（用于跳转结果页）
    video_ids_in_page = [row.video_id for row in rows]
    latest_task_map: dict[str, str] = {}
    if video_ids_in_page:
        task_rows = await db.execute(
            select(AnalysisTask.video_id, AnalysisTask.id)
            .where(
                AnalysisTask.video_id.in_(video_ids_in_page),
                AnalysisTask.user_id == user_id,
            )
            .order_by(AnalysisTask.created_at.desc())
        )
        for trow in task_rows.all():
            if trow.video_id not in latest_task_map:
                latest_task_map[trow.video_id] = trow.id

    items = []
    for row in rows:
        items.append({
            "video_id": row.video_id,
            "task_id": latest_task_map.get(row.video_id, ""),
            "title": row.title or "",
            "cover_url": row.cover_url or "",
            "url": row.url or "",
            "platform_video_id": row.platform_video_id or "",
            "platform": row.platform.value if hasattr(row.platform, "value") else str(row.platform),
            "author": row.author or "",
            "comment_count": row.comment_count or 0,
            "status": row.status.value if hasattr(row.status, "value") else str(row.status or "pending"),
            "last_analysis_date": row.last_analysis_date.strftime("%Y-%m-%d") if row.last_analysis_date else "",
            "publish_date": row.publish_time.strftime("%Y-%m-%d") if row.publish_time else "",
            "new_comments_since_tracking": 0,
        })

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

    return {
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "page_size": page_size,
        "items": items,
    }
