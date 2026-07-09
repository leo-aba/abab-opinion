"""评论表 — 对应数据库 comments 表

注意：模型属性名（Python）与实际数据库列名不完全一致，
通过 mapped_column 的第一个位置参数指定数据库列名。
"""

from datetime import datetime
from sqlalchemy import String, BigInteger, Integer, Float, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class Comment(Base):
    """平台评论 — 每条记录对应一条从平台抓取的一级评论"""
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, comment="UUID 主键"
    )
    cid: Mapped[str] = mapped_column(
        "platform_comment_id", String(64), nullable=False, comment="平台侧评论 ID（如 B站 rpid）"
    )
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id"), nullable=False, comment="所属视频 ID（FK → videos）"
    )
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("analysis_tasks.id"), nullable=True,
        comment="抓取该评论的分析任务 ID（可空，跨任务共享评论）"
    )
    text: Mapped[str] = mapped_column(
        "content", Text, nullable=False, comment="评论文本内容"
    )
    create_time: Mapped[datetime | None] = mapped_column(
        "publish_time", DateTime, nullable=True, comment="评论发布时间"
    )
    digg_count: Mapped[int] = mapped_column(
        "like_count", Integer, nullable=False, default=0, comment="点赞数"
    )
    reply_comment_total: Mapped[int] = mapped_column(
        "reply_count", Integer, nullable=False, default=0, comment="回复数"
    )
    user_uid: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="评论者平台 UID"
    )
    user_nickname: Mapped[str | None] = mapped_column(
        "author_name", String(128), nullable=True, comment="评论者昵称"
    )
    user_avatar: Mapped[str | None] = mapped_column(
        "author_avatar", String(512), nullable=True, comment="评论者头像 URL"
    )
    platform: Mapped[str] = mapped_column(
        String(16), nullable=False, default="bilibili", comment="平台: bilibili / douyin"
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, comment="抓取时间"
    )
    language: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="评论语言代码"
    )
    embedding_json: Mapped[str | None] = mapped_column(
        "embedding_json", Text, nullable=True, comment="JSON array of float values (embedding vector)"
    )
    sentiment: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="情感倾向: positive/negative/neutral"
    )
    sentiment_score: Mapped[float | None] = mapped_column(
        "sentiment_score", Float, nullable=True, comment="情感分数"
    )
    topic_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True,
        comment="所属话题 ID（FK → topics）"
    )
    is_cleaned: Mapped[bool] = mapped_column(
        "is_cleaned", Integer, nullable=False, default=0, comment="是否已清洗"
    )
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime, nullable=False, default=datetime.utcnow, comment="入库时间"
    )

    __table_args__ = (
        UniqueConstraint("platform_comment_id", "platform", name="uq_cid_platform"),
        Index("idx_comment_video_id", "video_id"),
        Index("idx_comment_task_id", "task_id"),
    )
