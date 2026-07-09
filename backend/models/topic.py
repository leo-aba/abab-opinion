"""话题表 — 对应数据库 topics 表"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Float, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Topic(Base):
    """聚类话题 — 每条记录对应一个分析任务产出的一个话题簇"""
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_tasks.id", ondelete="CASCADE"), nullable=False,
        comment="所属分析任务 ID"
    )
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False,
        comment="所属视频 ID"
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="话题名称"
    )
    comment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="该话题下的评论数"
    )
    percentage: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="话题评论占总评论比例"
    )
    keywords_json: Mapped[str | None] = mapped_column(
        "keywords_json", Text, nullable=True, comment='JSON array ["kw1","kw2",...]'
    )
    ai_summary: Mapped[str | None] = mapped_column(
        "ai_summary", Text, nullable=True, comment="AI 生成的话题摘要"
    )
    sentiment_distribution_json: Mapped[str | None] = mapped_column(
        "sentiment_distribution_json", Text, nullable=True,
        comment='{"positive":N,"negative":N,"neutral":N}'
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, comment="创建时间"
    )
