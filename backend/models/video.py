"""视频表 — 对应数据库 videos 表"""

import uuid
import enum
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Platform(str, enum.Enum):
    """视频平台"""
    bilibili = "bilibili"
    douyin = "douyin"


class AnalysisStatus(str, enum.Enum):
    """视频分析状态"""
    pending = "pending"
    analyzing = "analyzing"
    analyzed = "analyzed"
    tracking = "tracking"


class Video(Base):
    """视频元信息，每条记录对应一个已录入系统的视频"""
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    platform: Mapped[Platform] = mapped_column(
        SAEnum(Platform), nullable=False, comment="平台: bilibili / douyin"
    )
    platform_video_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="平台侧视频 ID（如 BV 号）"
    )
    title: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="视频标题"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="视频简介"
    )
    cover_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="视频封面图 URL"
    )
    uploader_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="上传者昵称"
    )
    uploader_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="上传者平台 ID"
    )
    url: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="视频页面 URL"
    )
    publish_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="发布时间"
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="视频时长（秒）"
    )
    comment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="评论数"
    )
    view_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="播放量"
    )
    like_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="点赞数"
    )
    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        SAEnum(AnalysisStatus), nullable=False, default=AnalysisStatus.pending,
        comment="分析状态: pending/analyzing/analyzed/tracking"
    )
    last_analysis_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最近一次分析时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, comment="入库时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
        comment="最近更新时间"
    )
