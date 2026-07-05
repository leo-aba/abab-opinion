"""分析任务 API — /api/analysis/*"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.analysis import CreateAnalysisRequest
from backend.schemas.common import ok
from backend.service.analysis_service import create_analysis_task

logger = logging.getLogger("analysis_api")

router = APIRouter(prefix="/api/analysis", tags=["分析任务"])


@router.post("/create", summary="创建分析任务")
async def create_analysis(
    body: CreateAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建分析任务。

    接收前端提交的分析参数，解析视频 URL，查找或创建视频记录，
    然后创建一条 AnalysisTask 记录（状态为 queued）。

    请求体字段:
      - mode:          分析模式 ('tracking' | 'normal')
      - video_title:   视频标题（前端展示用，服务端不使用）
      - video_url:     视频页面 URL
      - comment_count: 评论数量上限 (int, 0=全部)
      - time_range:    前端时间范围文案 ('最近500条' / '最近7天' / 等)
      - language:      语言过滤 ('all')

    返回:
      {task_id: str, status: "queued"}
    """
    try:
        task = await create_analysis_task(
            db=db,
            user_id=current_user.id,
            mode=body.mode,
            video_url=body.video_url,
            comment_count=body.comment_count,
            time_range=body.time_range,
            language=body.language,
        )
        logger.info(
            "用户 %s 创建分析任务 %s (mode=%s, video=%s)",
            current_user.username, task.id, body.mode, task.video_id,
        )
        return ok({"task_id": task.id, "status": "queued"})

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
