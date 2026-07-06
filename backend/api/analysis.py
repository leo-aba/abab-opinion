"""分析任务 API — /api/analysis/*"""

import asyncio
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from backend.database import get_db, get_sessionmaker
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.models.analysis_task import AnalysisTask, AnalysisStatus
from backend.schemas.analysis import CreateAnalysisRequest
from backend.schemas.common import ok
from backend.service.analysis_service import create_analysis_task

logger = logging.getLogger("analysis_api")

router = APIRouter(prefix="/api/analysis", tags=["分析任务"])


@router.post("/create", summary="创建分析任务")
async def create_analysis(
    body: CreateAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建分析任务。

    接收前端提交的分析参数，解析视频 URL，查找或创建视频记录，
    然后创建一条 AnalysisTask 记录（状态为 queued），并在后台
    异步抓取评论。

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
            background_tasks=background_tasks,
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


@router.get("/{task_id}/progress", summary="查询分析任务进度")
async def get_task_progress(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询分析任务进度，供前端 pipeline 页轮询。

    返回富进度结构:
      {
        overall_pct: 0-100,
        overall_hint: str,
        steps: [{step, name, state}],
        logs: [{time, message, type}],
        status: str,
      }
    """
    task = await db.get(AnalysisTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")

    # 映射状态到前端 steps
    status = task.status.value if hasattr(task.status, 'value') else task.status
    steps = _build_steps(status, task.progress_pct)

    # 构建 overall_hint
    hint = _build_hint(status, task.progress_pct, task.total_comments_processed, task.comment_limit)

    # 构建日志
    logs = _build_logs(status, task)

    return ok({
        "overall_pct": task.progress_pct,
        "overall_hint": hint,
        "steps": steps,
        "logs": logs,
        "status": status,
    })


def _build_steps(status: str, progress_pct: int) -> list[dict]:
    """根据任务状态构建 pipeline 步骤列表"""
    # 步骤定义
    step_defs = [
        (1, "抓取评论"),
        (2, "清洗数据"),
        (3, "向量化"),
        (4, "聚类分析"),
        (5, "Topic 生成"),
        (6, "AI 总结"),
    ]

    # 已完成步骤数（基于 progress_pct 估算）
    if status == "completed":
        done_count = 6
    elif status == "failed":
        # 如果失败在收集阶段，done_count 为 0
        done_count = 0 if progress_pct < 10 else 1
    elif status == "collecting":
        done_count = 0
    else:
        done_count = 0

    steps = []
    for step_num, step_name in step_defs:
        if step_num <= done_count:
            state = "done"
        elif step_num == done_count + 1 and (status == "collecting" or status == "completed" or (status == "failed" and step_num == 1)):
            state = "running" if status != "failed" else "done"
        else:
            state = "waiting"

        # 如果进度 > 0 且状态是 queued，第1步 running
        if status == "queued" and progress_pct > 0 and step_num == 1:
            state = "running"

        steps.append({"step": step_num, "name": step_name, "state": state})

    return steps


def _build_hint(status: str, progress_pct: int, processed: int, limit: int) -> str:
    """构建进度提示文案"""
    if status == "queued":
        return "任务已创建，等待调度..."
    elif status == "collecting":
        if limit > 0:
            return f"正在抓取评论 ({processed}/{limit})..."
        else:
            return f"正在抓取评论 (已处理 {processed} 条)..."
    elif status == "completed":
        return "分析完成！"
    elif status == "failed":
        return "分析任务失败"
    else:
        return f"处理中... ({progress_pct}%)"


def _build_logs(status: str, task: AnalysisTask) -> list[dict]:
    """构建进度日志"""
    import datetime
    now = datetime.datetime.now().strftime("%H:%M:%S")
    logs = []

    logs.append({"time": task.created_at.strftime("%H:%M:%S") if task.created_at else now, "message": "任务已创建", "type": "info"})

    if status == "collecting" or status == "completed":
        logs.append({"time": now, "message": f"开始抓取评论...", "type": "info"})
        if task.total_comments_processed > 0:
            logs.append({"time": now, "message": f"已完成抓取，共 {task.total_comments_processed} 条", "type": "success"})

    if status == "completed":
        logs.append({"time": now, "message": "分析任务全部完成", "type": "success"})

    if status == "failed" and task.error_message:
        logs.append({"time": now, "message": f"失败: {task.error_message}", "type": "error"})

    return logs


# ──────────────────────────────────────────────
# SSE 实时进度推送
# ──────────────────────────────────────────────

async def _get_current_user_sse(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """SSE 端点专用鉴权：优先取 query param ?token=，其次取 Authorization header。

    EventSource 无法自定义请求头，因此 token 通过 query 传递。
    """
    token = request.query_params.get("token")
    if not token:
        # fallback: 尝试从 Authorization header 读取
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]

    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    from jose import jwt, JWTError
    from backend.config import JWT_SECRET, JWT_ALGORITHM
    from backend.models.user import User

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="无效的 Token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 已过期或无效")

    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


@router.get("/{task_id}/stream", summary="SSE 实时进度推送")
async def stream_analysis_progress(
    task_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_get_current_user_sse),
):
    """SSE (Server-Sent Events) 端点，供 pipeline.html 实时展示分析进度。

    前端使用 EventSource 连接：
        new EventSource('/api/analysis/{taskId}/stream?token=' + token)

    事件类型:
      - progress: {overall_pct, overall_hint, steps, status}
      - log:      {time, message, type}
      - complete: {}
      - error:    {message}

    每 2 秒轮询一次任务状态，连接断开时自动退出。
    """
    # 验证任务所有权
    task = await db.get(AnalysisTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")

    async def event_stream():
        last_log_count = 0
        last_status = None

        while True:
            # 检查客户端是否断开
            if await request.is_disconnected():
                break

            # 打开独立 session 查询最新状态
            async with get_sessionmaker()() as sess:
                fresh = await sess.get(AnalysisTask, task_id)
                if fresh is None:
                    break

                status = fresh.status.value if hasattr(fresh.status, 'value') else fresh.status
                pct = fresh.progress_pct

                # ── progress event ──
                steps = _build_steps(status, pct)
                hint = _build_hint(status, pct, fresh.total_comments_processed, fresh.comment_limit)
                progress_data = {
                    "overall_pct": pct,
                    "overall_hint": hint,
                    "steps": steps,
                    "logs": _build_logs(status, fresh),
                    "status": status,
                }
                yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"

                # ── log event（增量推送）──
                logs = _build_logs(status, fresh)
                for i in range(last_log_count, len(logs)):
                    yield f"event: log\ndata: {json.dumps(logs[i])}\n\n"
                last_log_count = len(logs)

                # ── complete / error event ──
                if status == "completed" and last_status != "completed":
                    yield "event: complete\ndata: {}\n\n"
                    break
                if status == "failed" and last_status != "failed":
                    err_msg = fresh.error_message or "分析任务失败"
                    yield f"event: error\ndata: {json.dumps({'message': err_msg})}\n\n"
                    break

                last_status = status

            # 每 2 秒轮询
            await asyncio.sleep(2)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

