"""视频相关 API — 视频搜索、列表查询"""

import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.common import ok
from backend.service.video_service import search_video_by_url

logger = logging.getLogger("video_api")

router = APIRouter(prefix="/api/videos", tags=["视频"])


@router.get("/search", summary="搜索视频")
async def search_videos(
    query: str = Query(..., min_length=1, description="视频 URL（Bilibili / 抖音）"),
    platform: str = Query(default="", description="平台标识，留空则自动识别"),
    type: str = Query(default="url", description="搜索类型，目前仅支持 url"),
    db: AsyncSession = Depends(get_db),
):
    """根据视频 URL 搜索视频信息。

    优先从数据库查询已录入的视频；如果未找到，则实时调用平台 API
    抓取视频元信息并自动入库后返回。

    平台识别规则（自动从 URL 判断，无需手动指定 platform）：
      - 包含 bilibili.com/video/BVxxx 或裸 BV 号 → Bilibili
      - 包含 douyin.com/video/数字ID → 抖音

    返回格式（数组，通常只有一条）：
      [{video_id, title, cover_url, uploader, comment_count}]
    """
    try:
        results = await search_video_by_url(query, db)
        return ok(results)
    except ValueError as e:
        # URL 格式无法识别 → 400
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # 平台 API 错误等 → 502
        raise HTTPException(status_code=502, detail=str(e))
