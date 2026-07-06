"""用户操作相关 — 请求体校验"""

from pydantic import BaseModel, Field


class UpdateUsernameRequest(BaseModel):
    password: str = Field(min_length=1, description="当前密码")
    new_username: str = Field(min_length=3, description="新用户名（>=3 位）")


class UpdateEmailRequest(BaseModel):
    password: str = Field(min_length=1, description="当前密码")
    new_email: str = Field(min_length=1, description="新邮箱")


class UpdatePasswordRequest(BaseModel):
    password: str = Field(min_length=1, description="当前密码")
    new_password: str = Field(min_length=6, description="新密码（>=6 位）")
