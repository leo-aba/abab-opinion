"""设置相关 — 响应体 Pydantic 模型"""

from pydantic import BaseModel


class AnalysisPreferences(BaseModel):
    default_comment_count: int = 500
    auto_ai_summary: bool = True
    realtime_animation: bool = True


class NotificationPreferences(BaseModel):
    analysis_complete_notify: bool = True
    anomaly_alert: bool = True


class AccountInfo(BaseModel):
    username: str
    email: str | None = None


class SettingsResponse(BaseModel):
    analysis_preferences: AnalysisPreferences
    notification_preferences: NotificationPreferences
    account: AccountInfo


class SettingsData(BaseModel):
    """GET /api/settings 返回的 data 字段"""
    analysis_preferences: AnalysisPreferences
    notification_preferences: NotificationPreferences
    account: AccountInfo
