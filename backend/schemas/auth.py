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


class SendResetCodeRequest(BaseModel):
    """POST /api/auth/send-reset-code 请求体"""
    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    email: str = Field(..., min_length=1, max_length=128, description="注册邮箱")


class VerifyResetCodeRequest(BaseModel):
    """POST /api/auth/reset-password 请求体"""
    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    code: str = Field(..., min_length=6, max_length=6, description="验证码")
    password: str = Field(..., min_length=6, max_length=128, description="新密码")
    confirm_password: str = Field(..., min_length=6, max_length=128, description="确认新密码")
