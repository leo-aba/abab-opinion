"""邮件报告 Service — 组装分析数据 + 生成 HTML + 发送邮件"""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.service.email_service import send_email
from backend.models.analysis_task import AnalysisTask
from backend.models.user import User
from backend.models.video import Video
from backend.models.topic import Topic
from backend.models.tracking_task import TrackingTask
from backend.models.user_settings import UserSettings

logger = logging.getLogger("report_service")


# ──────────────────────────────────────────────
# HTML 构建工具
# ──────────────────────────────────────────────

def _build_sentiment_bar(pos_pct: float, neu_pct: float, neg_pct: float) -> str:
    """构建情感分布三色进度条 HTML — 网站配色：橙=正面, 青=中性, 中性灰=负面"""
    if abs(pos_pct + neu_pct + neg_pct) < 0.01:
        return "<p style='color:#666;'>暂无情感数据</p>"
    return (
        '<div style="display:flex;height:20px;border-radius:10px;overflow:hidden;'
        'margin:12px 0;font-size:11px;font-weight:600;color:#fff;text-align:center;line-height:20px;">'
        f'<div style="flex:{pos_pct};background:#00B4CC;">'
        f'{"正面 " + str(pos_pct) + "%" if pos_pct > 8 else ""}</div>'
        f'<div style="flex:{neu_pct};background:#BFB59E;">'
        f'{"中性 " + str(neu_pct) + "%" if neu_pct > 8 else ""}</div>'
        f'<div style="flex:{neg_pct};background:#FF7A22;">'
        f'{"负面 " + str(neg_pct) + "%" if neg_pct > 8 else ""}</div>'
        '</div>'
        '<div style="font-size:12px;color:#BFB59E;display:flex;justify-content:space-between;padding:0 4px;">'
        f'<span>正面 {pos_pct}%</span>'
        f'<span>中性 {neu_pct}%</span>'
        f'<span>负面 {neg_pct}%</span>'
        '</div>'
    )


# ──────────────────────────────────────────────
# 报告 HTML 生成（xc 分支风格：Python 拼 HTML，不用模板）
# ──────────────────────────────────────────────

async def generate_report_html(db: AsyncSession, task_id: str, is_periodic: bool = False) -> str:
    """生成分析报告 HTML 邮件正文。

    配色与网站一致：奶油底色 #F8F2E4 + 黑色卡片 + 橙色 #FF7A22 / 青色 #00B4CC 强调。
    纯扁平设计，无渐变无阴影。
    """
    # ── 查 Task + Video + User ──
    task = await db.get(AnalysisTask, task_id)
    if not task:
        raise ValueError(f"分析任务不存在: {task_id}")

    video = await db.get(Video, task.video_id)
    user = await db.get(User, task.user_id)

    video_title = video.title if video else "未知视频"
    video_uploader = video.uploader_name if video else ""
    vp = video.platform if video else ""
    video_platform = vp.value if hasattr(vp, "value") else str(vp) if vp else ""
    video_url = video.url if video else ""

    total_comments = task.total_comments_processed or 0
    topic_count = task.topic_count or 0
    username = user.username if user else "用户"

    # ── 话题列表 ──
    topics_result = await db.execute(
        select(Topic).where(Topic.task_id == task_id)
        .order_by(Topic.comment_count.desc())
    )
    topics = topics_result.scalars().all()

    # ── 情感统计 ──
    pos_total = neg_total = neu_total = 0
    for t in topics:
        sdj = t.sentiment_distribution_json
        if sdj:
            try:
                dist = json.loads(sdj) if isinstance(sdj, str) else sdj
                pos_total += dist.get("positive", 0)
                neg_total += dist.get("negative", 0)
                neu_total += dist.get("neutral", 0)
            except (json.JSONDecodeError, TypeError):
                pass

    grand = pos_total + neg_total + neu_total
    if grand > 0:
        pos_pct = round(pos_total / grand * 100, 1)
        neg_pct = round(neg_total / grand * 100, 1)
        neu_pct = round(neu_total / grand * 100, 1)
    else:
        pos_pct = neg_pct = neu_pct = 0

    # ── 整体 AI 总结 ──
    overall_summary = ""
    if task.error_message:
        try:
            ed = json.loads(task.error_message)
            overall_summary = ed.get("ai_summary") or ed.get("overall_summary", "")
        except (json.JSONDecodeError, TypeError):
            pass

    # ── 情感条 HTML ──
    sentiment_html = _build_sentiment_bar(pos_pct, neu_pct, neg_pct)

    # ── 话题卡片 HTML ──
    topics_html = ""
    for t in topics:
        keywords = []
        if t.keywords_json:
            try:
                keywords = json.loads(t.keywords_json) if isinstance(t.keywords_json, str) else t.keywords_json
            except (json.JSONDecodeError, TypeError):
                pass
        kw_str = "、".join(keywords[:5]) if keywords else ""
        summary = t.ai_summary or ""
        topics_html += (
            '<div style="background:#F8F2E4;border:1px solid #FF7A22;border-radius:14px;'
            'padding:16px;margin-bottom:12px;">'
            f'<h4 style="margin:0 0 6px;font-size:15px;color:#000;">{t.name}</h4>'
            '<div style="font-size:12px;color:#666;margin-bottom:6px;">'
            f'评论数: <strong style="color:#FF7A22;">{t.comment_count}</strong> 条 '
            f'| 占比: <strong>{t.percentage}%</strong></div>'
        )
        if kw_str:
            topics_html += (
                f'<div style="font-size:12px;color:#666;margin-bottom:6px;">'
                f'关键词: <span style="color:#00B4CC;">{kw_str}</span></div>'
            )
        if summary:
            topics_html += (
                '<div style="font-size:13px;color:#000;padding:10px;background:#fff;'
                f'border-radius:10px;border:2px solid #000;">{summary}</div>'
            )
        topics_html += '</div>'

    # ── AI 总结区域 ──
    summary_section = ""
    if overall_summary:
        summary_section = (
            '<tr><td style="padding:8px 32px 24px;">'
            '<h3 style="margin:0 0 12px;font-size:16px;color:#F8F2E4;">AI 综合分析</h3>'
            '<div style="background:#F8F2E4;border:2px solid #00B4CC;border-radius:14px;'
            f'padding:16px;font-size:13px;color:#000;line-height:1.7;">{overall_summary}</div></td></tr>'
        )

    # ── 视频信息行 ──
    uploader_html = f"作者: {video_uploader} &nbsp;|&nbsp; " if video_uploader else ""
    link_html = (
        f'<a href="{video_url}" style="color:#00B4CC;text-decoration:none;font-weight:600;">'
        f'查看原视频 &rarr;</a>'
        if video_url else ""
    )

    # ── 周期性 vs 首次 的标题文案 ──
    hero_title = "追踪分析更新" if is_periodic else "分析报告已生成"
    hero_sub = "AI Opinion Analytics · 实时追踪更新报告" if is_periodic else "AI Opinion Analytics · 视频评论分析报告"
    intro_text = "您的实时追踪发现了新的分析数据，以下为最新报告：" if is_periodic else "您的视频评论分析已完成，以下为分析报告详情："

    # ── 组装完整 HTML ──
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F8F2E4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F8F2E4;padding:24px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#000;border-radius:18px;overflow:hidden;border:2px solid #FF7A22;">
    <tr><td style="background:#FF7A22;padding:28px 32px 20px;text-align:center;">
        <h1 style="margin:0;font-size:22px;font-weight:800;color:#000;letter-spacing:0.5px;">{hero_title}</h1>
        <p style="margin:6px 0 0;font-size:13px;color:#000;opacity:0.7;">{hero_sub}</p>
    </td></tr>
    <tr><td style="padding:20px 32px 8px;">
        <p style="margin:0;font-size:14px;color:#F8F2E4;">尊敬的 <strong style="color:#FF7A22;">{username}</strong>，您好！</p>
        <p style="margin:6px 0 0;font-size:13px;color:#BFB59E;">{intro_text}</p>
    </td></tr>
    <tr><td style="padding:12px 32px;">
        <div style="background:#1A1A1A;border:1px solid #FF7A22;border-radius:14px;padding:16px;">
            <h3 style="margin:0 0 6px;font-size:16px;color:#F8F2E4;font-weight:700;">{video_title}</h3>
            <div style="font-size:12px;color:#BFB59E;">
                {uploader_html}平台: {video_platform} &nbsp;|&nbsp; {link_html}
            </div>
        </div>
    </td></tr>
    <tr><td style="padding:8px 32px;">
        <h3 style="margin:0 0 12px;font-size:16px;color:#F8F2E4;font-weight:700;">数据概览</h3>
        <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
            <td width="33%" style="text-align:center;padding:12px 8px;">
                <div style="font-size:28px;font-weight:800;color:#FF7A22;">{total_comments}</div>
                <div style="font-size:11px;color:#BFB59E;margin-top:4px;">评论总数</div>
            </td>
            <td width="33%" style="text-align:center;padding:12px 8px;">
                <div style="font-size:28px;font-weight:800;color:#00B4CC;">{topic_count}</div>
                <div style="font-size:11px;color:#BFB59E;margin-top:4px;">话题数量</div>
            </td>
            <td width="33%" style="text-align:center;padding:12px 8px;">
                <div style="font-size:28px;font-weight:800;color:#F8F2E4;">{pos_pct}%</div>
                <div style="font-size:11px;color:#BFB59E;margin-top:4px;">正面占比</div>
            </td>
        </tr>
        </table>
    </td></tr>
    <tr><td style="padding:8px 32px;">
        <h3 style="margin:0 0 4px;font-size:16px;color:#F8F2E4;font-weight:700;">情感分布</h3>
        {sentiment_html}
    </td></tr>
    <tr><td style="padding:16px 32px;">
        <h3 style="margin:0 0 12px;font-size:16px;color:#F8F2E4;font-weight:700;">话题分析</h3>
        {topics_html if topics_html else '<p style="color:#BFB59E;font-size:13px;">暂无话题数据</p>'}
    </td></tr>
    {summary_section}
    <tr><td style="border-top:2px solid #FF7A22;padding:20px 32px;text-align:center;">
        <p style="margin:0;font-size:11px;color:#666;">由 AI Opinion Analytics 自动发送</p>
    </td></tr>
</table>
</td></tr></table>
</body>
</html>"""
    return html


# ──────────────────────────────────────────────
# 发送报告邮件
# ──────────────────────────────────────────────

async def send_report_email(user_email: str, report_data: dict) -> bool:
    """发送报告邮件。

    Args:
        user_email: 收件人邮箱
        report_data: build_report_data() 返回的数据字典（含 _html_body 键）

    Returns:
        True 发送成功，False 失败
    """
    html_body = report_data.get("_html_body", "")
    if not html_body:
        logger.error("报告 HTML 为空，无法发送")
        return False

    subject = f"【AI Opinion Analytics】分析报告已生成"

    return send_email(
        to_address=user_email,
        subject=subject,
        html_body=html_body,
    )


# ──────────────────────────────────────────────
# 组装报告数据
# ──────────────────────────────────────────────

async def build_report_data(db: AsyncSession, task_id: str) -> dict:
    """组装报告所需的全部数据 + HTML，返回字典。

    Args:
        db: 数据库 session
        task_id: 分析任务 ID

    Returns:
        包含报告数据 + _html_body 键的 dict
    """
    # 查用户名
    task = await db.get(AnalysisTask, task_id)
    user = await db.get(User, task.user_id) if task else None
    video = await db.get(Video, task.video_id) if task else None

    report_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    username = user.username if user else ""

    # 生成 xc 风格的 HTML
    html_body = await generate_report_html(db, task_id)

    return {
        "_html_body": html_body,
        "report_time": report_time,
        "username": username,
        "video_title": video.title if video else "",
        "video_platform": (
            video.platform.value
            if video and hasattr(video.platform, "value")
            else str(video.platform) if video else ""
        ),
        "video_uploader": video.uploader_name if video else "",
        "video_url": video.url if video else "",
        "total_comments": task.total_comments_processed if task else 0,
        "topic_count": task.topic_count if task else 0,
    }


# ──────────────────────────────────────────────
# 频率限制（内存 dict）
# ──────────────────────────────────────────────

_send_timestamps: dict[str, float] = {}  # key: "{user_id}:{task_id}" → timestamp


def check_rate_limit(user_id: str, task_id: str) -> Optional[int]:
    """检查发送频率限制。同一用户+同一任务，60 秒内只能发送一次。"""
    import time
    key = f"{user_id}:{task_id}"
    now = time.time()
    last = _send_timestamps.get(key, 0)
    if now - last < 60:
        return int(60 - (now - last))
    return None


def mark_rate_limit(user_id: str, task_id: str) -> None:
    """记录发送时间戳。"""
    import time
    key = f"{user_id}:{task_id}"
    _send_timestamps[key] = time.time()


# ──────────────────────────────────────────────
# 自动发送（分析完成时调用）
# ──────────────────────────────────────────────

async def try_auto_send_report(
    db: AsyncSession,
    task_id: str,
    user_id: str,
    user_email: Optional[str],
    notify_on_complete: bool,
) -> bool:
    """分析完成时尝试自动发送报告邮件。

    此函数设计为独立调用，自行处理所有异常，不抛出。
    """
    if not notify_on_complete:
        logger.info("自动发送跳过: 用户未开启通知 (user_id=%s)", user_id)
        return False

    if not user_email:
        logger.info("自动发送跳过: 用户未绑定邮箱 (user_id=%s)", user_id)
        return False

    try:
        report_data = await build_report_data(db, task_id)
        ok_result = await send_report_email(user_email, report_data)
        if ok_result:
            logger.info("自动发送报告成功: task_id=%s -> %s", task_id, user_email)
            return True
        else:
            logger.error("自动发送报告失败: task_id=%s -> %s", task_id, user_email)
            return False
    except Exception as e:
        logger.error("自动发送报告异常: task_id=%s, error=%s", task_id, e)
        return False


# ──────────────────────────────────────────────
# 周期性报告（实时追踪模式专用）
# ──────────────────────────────────────────────

async def try_send_periodic_report(
    db: AsyncSession,
    tracking: TrackingTask,
    user: User,
    user_settings: UserSettings | None,
) -> bool:
    """追踪循环中调用：间隔足够且有新分析数据时发送更新报告。

    此函数设计为独立调用，自行处理所有异常，不抛出。

    Args:
        db: 当前轮询循环中的数据库 session
        tracking: TrackingTask ORM 对象（已在 session 中加载）
        user: User ORM 对象
        user_settings: UserSettings（可为 None，使用默认值）

    Returns:
        True 已发送，False 跳过或失败
    """
    try:
        # 1) 检查通知开关
        if user_settings and not user_settings.notify_on_complete:
            return False

        # 2) 检查邮箱
        if not user.email:
            return False

        # 3) 间隔：默认 30 分钟，最小 5 分钟
        interval_mins = max(5, user_settings.report_interval_minutes if user_settings else 30)

        # 4) 检查是否距上次发送足够久
        now = datetime.utcnow()
        if tracking.last_report_at is not None:
            elapsed = (now - tracking.last_report_at).total_seconds() / 60
            if elapsed < interval_mins:
                return False  # 间隔未到

        # 5) 检查是否有新分析数据
        if tracking.last_report_at is not None and tracking.last_analyzed_at is not None:
            if tracking.last_analyzed_at <= tracking.last_report_at:
                logger.debug("周期性报告跳过: 无新分析数据 (tracking_id=%s)", tracking.id)
                return False

        # 6) 生成 HTML 并发送
        html_body = await generate_report_html(db, tracking.analysis_task_id, is_periodic=True)
        subject = "【AI Opinion Analytics】追踪分析更新"

        success = send_email(user.email, subject, html_body)
        if success:
            tracking.last_report_at = now
            logger.info("周期性报告发送成功: tracking_id=%s -> %s", tracking.id, user.email)
            return True
        else:
            logger.error("周期性报告发送失败: tracking_id=%s -> %s", tracking.id, user.email)
            return False

    except Exception as e:
        logger.error("周期性报告异常 (tracking_id=%s): %s", tracking.id, e, exc_info=True)
        return False
