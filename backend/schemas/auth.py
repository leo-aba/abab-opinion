"""认证相关 — 请求体校验"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    remember: bool = False


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3)
    email: str = Field(...)
    password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)
