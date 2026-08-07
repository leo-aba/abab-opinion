"""追踪任务表 — 对应数据库 tracking_tasks 表"""

import uuid
import enum
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Float, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class TrackingStatus(str, enum.Enum):
    """追踪任务状态"""
    active = "active"
    paused = "paused"
    stopped = "stopped"
    exhausted = "exhausted"


class TrackingTask(Base):
    __tablename__ = "tracking_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    analysis_task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_tasks.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联的分析任务 ID",
    )
    video_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        comment="目标视频 ID",
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建者 ID",
    )
    status: Mapped[TrackingStatus] = mapped_column(
        SAEnum(TrackingStatus), nullable=False, default=TrackingStatus.active,
        comment="追踪状态: active / paused / stopped / exhausted"
    )
    poll_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=120, comment="轮询间隔（秒）"
    )
    new_comments_since_start: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="追踪启动以来新增评论数"
    )
    credits_consumed: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="已消耗积分"
    )
    credits_rate_per_hour: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, comment="每小时积分消耗率"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, comment="追踪开始时间"
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="追踪停止时间"
    )
    last_poll_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="上次轮询时间"
    )
    last_comment_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="上次抓取的最新平台评论 ID（用于增量轮询）"
    )
    last_analyzed_comment_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="上次 LLM 增量分析过的最新评论 cid"
    )
    last_analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="上次 LLM 增量分析时间"
    )
    last_report_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="上次报告邮件发送时间"
    )
