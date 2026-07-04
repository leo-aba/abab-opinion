"""视频相关 Pydantic 模型 — 请求参数 & 响应结构"""

from pydantic import BaseModel, Field


class VideoSearchItem(BaseModel):
    """单条视频搜索结果 — 对应前端 searchVideos() 的返回格式"""
    video_id: str = Field(..., description="视频 UUID（videos 表主键）")
    title: str = Field(..., description="视频标题")
    cover_url: str | None = Field(None, description="封面图 URL")
    uploader: str | None = Field(None, description="上传者昵称（映射 uploader_name，前端字段用 uploader）")
    comment_count: int = Field(0, description="评论总数")
