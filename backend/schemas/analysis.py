"""分析任务相关 Pydantic 模型 — 请求体 & 响应结构"""

from pydantic import BaseModel, Field, model_validator


class CreateAnalysisRequest(BaseModel):
    """POST /api/analysis/create 请求体"""
    mode: str = Field(..., description="分析模式: 'tracking' | 'normal'")
    video_title: str = Field(default="", description="前端选中的视频标题（冗余，便于日志）")
    video_url: str = Field(..., min_length=1, description="视频页面 URL")
    comment_count: int = Field(default=500, ge=0, description="评论数量上限，0=全部")
    time_range: str = Field(default="最近500条", description="前端时间范围文案")
    language: str = Field(default="all", description="语言过滤: 'all' | 'zh' | 'en'")

    @model_validator(mode="after")
    def validate_mode(self):
        if self.mode not in ("tracking", "normal"):
            raise ValueError(f"不支持的分析模式: {self.mode}")
        return self
