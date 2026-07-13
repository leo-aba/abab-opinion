"""用户设置表 — 对应数据库 user_settings 表"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    default_comment_count: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    auto_generate_summary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    realtime_animation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_complete: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_anomaly: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    report_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, comment="追踪期间报告邮件发送间隔（分钟）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
