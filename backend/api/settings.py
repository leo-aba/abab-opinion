"""设置接口 — /api/settings/*"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.models.user_settings import UserSettings
from backend.schemas.common import ok
from backend.schemas.settings import SettingsData, AnalysisPreferences, NotificationPreferences, AccountInfo

logger = logging.getLogger("settings")

router = APIRouter(prefix="/api/settings", tags=["设置"])


def _build_response(user: User, settings: UserSettings | None) -> dict:
    """将 User + UserSettings ORM 组装为前端期望的嵌套结构"""
    if settings:
        ap = AnalysisPreferences(
            default_comment_count=settings.default_comment_count,
            auto_ai_summary=settings.auto_generate_summary,
            realtime_animation=settings.realtime_animation,
        )
        np = NotificationPreferences(
            analysis_complete_notify=settings.notify_on_complete,
            anomaly_alert=settings.notify_on_anomaly,
        )
    else:
        # 无记录时返回全默认值
        ap = AnalysisPreferences()
        np = NotificationPreferences()

    account = AccountInfo(
        username=user.username,
        email=user.email,
    )

    return SettingsData(
        analysis_preferences=ap,
        notification_preferences=np,
        account=account,
    ).model_dump()


@router.get("")
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的全部设置"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    logger.debug('用户"%s"获取设置%s', current_user.username, ' (已有记录)' if settings else ' (无记录，返回默认值)')
    return ok(_build_response(current_user, settings))
