"""设置相关 — 响应体 Pydantic 模型"""

from pydantic import BaseModel


class AnalysisPreferences(BaseModel):
    default_comment_count: int = 500


class NotificationPreferences(BaseModel):
    analysis_complete_notify: bool = True
    report_interval_minutes: int = 30


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


class UpdateAnalysisPreferencesRequest(BaseModel):
    """PUT /api/settings/analysis-preferences — 所有字段可选，只更新传入的"""
    default_comment_count: int | None = None


class UpdateNotificationPreferencesRequest(BaseModel):
    """PUT /api/settings/notification-preferences — 所有字段可选，只更新传入的"""
    analysis_complete_notify: bool | None = None
    report_interval_minutes: int | None = None
