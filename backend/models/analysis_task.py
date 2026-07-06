"""分析任务表 — 对应数据库 analysis_tasks 表"""

import uuid
import enum
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AnalysisMode(str, enum.Enum):
    """分析模式"""
    normal = "normal"
    tracking = "tracking"


class AnalysisStatus(str, enum.Enum):
    """分析任务状态（Pipeline 阶段）"""
    queued = "queued"
    collecting = "collecting"
    cleaning = "cleaning"
    embedding = "embedding"
    clustering = "clustering"
    topic_gen = "topic_gen"
    summarizing = "summarizing"
    completed = "completed"
    failed = "failed"


class TimeRange(str, enum.Enum):
    """时间范围"""
    d7 = "7d"
    d30 = "30d"
    all = "all"


class LanguageFilter(str, enum.Enum):
    """语言过滤"""
    zh = "zh"
    en = "en"
    all = "all"


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), nullable=False, comment="创建者 ID（FK → users）"
    )
    video_id: Mapped[str] = mapped_column(
        String(36), nullable=False, comment="目标视频 ID（FK → videos）"
    )
    platform: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="平台: bilibili / douyin"
    )
    mode: Mapped[AnalysisMode] = mapped_column(
        SAEnum(AnalysisMode), nullable=False, comment="分析模式: normal / tracking"
    )
    comment_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=500, comment="评论抓取数量上限（0=全部）"
    )
    time_range: Mapped[TimeRange] = mapped_column(
        SAEnum(TimeRange), nullable=False, default=TimeRange.d7,
        comment="时间范围: 7d / 30d / all"
    )
    language_filter: Mapped[LanguageFilter] = mapped_column(
        SAEnum(LanguageFilter), nullable=False, default=LanguageFilter.all,
        comment="语言过滤: zh / en / all"
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        SAEnum(AnalysisStatus), nullable=False, default=AnalysisStatus.queued,
        comment="任务状态: queued → collecting → cleaning → embedding → clustering → topic_gen → summarizing → completed / failed"
    )
    progress_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="完成百分比 (0-100)"
    )
    total_comments_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="已处理评论数"
    )
    topic_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="发现的 Topic 数量"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="失败时的错误信息"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="开始时间"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="完成时间"
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="总耗时（毫秒）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, comment="创建时间"
    )
