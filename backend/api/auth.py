"""认证接口 — /api/auth/*

前端调用:
  POST /api/auth/login     → api.login(username, password, remember)
  POST /api/auth/register  → api.register(username, email, password)
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.auth import LoginRequest, RegisterRequest, SendResetCodeRequest, VerifyResetCodeRequest
from backend.schemas.common import ok
from backend.service.auth_service import hash_password, verify_password, create_access_token
from backend.service.email_service import send_email

logger = logging.getLogger("auth")

router = APIRouter(prefix="/api/auth", tags=["认证"])

# DB 角色 → 前端显示名称
_ROLE_LABELS = {
    "admin": "管理员",
    "analyst": "分析师",
    "viewer": "观察者",
}


def _user_to_frontend(user: User) -> dict:
    """将 User ORM 对象转为前端期望的格式"""
    return {
        "user_id": user.id,
        "username": user.username,
        "role": _ROLE_LABELS.get(user.role.value if hasattr(user.role, "value") else user.role, user.role),
        "avatar_initial": user.username[0].upper() if user.username else "U",
        "email": user.email,
    }


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录：验证明文密码，签发 JWT，返回用户信息"""
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        logger.warning('用户"%s"登录失败: 用户名或密码错误', body.username)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    # 记住我 → 30 天有效期；否则使用全局默认（24 小时）
    token = create_access_token(user.id, 30 * 24 * 3600 if body.remember else None)
    logger.info('用户"%s"登录成功', body.username)
    return ok({
        "token": token,
        "user": _user_to_frontend(user),
    })


@router.post("/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册：校验输入、去重检查、创建用户并入库"""
    if body.password != body.confirm_password:
        logger.warning('注册失败: 两次密码不一致 (username="%s")', body.username)
        raise HTTPException(status_code=422, detail="两次密码不一致")
    if len(body.username) < 3:
        raise HTTPException(status_code=422, detail="用户名至少需要3位")
    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="密码至少需要6位")

    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        logger.warning('注册失败: 用户名已存在 "%s"', body.username)
        raise HTTPException(status_code=409, detail="用户名已存在")

    if body.email:
        existing_email = await db.execute(select(User).where(User.email == body.email))
        if existing_email.scalar_one_or_none():
            logger.warning('注册失败: 邮箱已被注册 "%s"', body.email)
            raise HTTPException(status_code=409, detail="邮箱已被注册")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()

    logger.info('新用户"%s"注册成功', body.username)
    return ok(None, "注册成功")


# 内存中存储验证码: {email: {code, expires_at, sent_at, user_id}}
_reset_codes: dict[str, dict] = {}


@router.post("/send-reset-code")
async def send_reset_code(
    body: SendResetCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    import time
    import random

    # 根据用户名查找用户，并校验邮箱匹配
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not user.email:
        logger.warning("发送验证码: 用户名 %s 不存在或未绑定邮箱", body.username)
        raise HTTPException(status_code=400, detail="用户名或邮箱不正确")

    if user.email.lower() != body.email.lower().strip():
        logger.warning("发送验证码: 邮箱不匹配 username=%s, input=%s, db=%s", body.username, body.email, user.email)
        raise HTTPException(status_code=400, detail="用户名或邮箱不正确")

    email = user.email
    now = time.time()
    existing = _reset_codes.get(body.username)
    if existing and now - existing.get("sent_at", 0) < 60:
        remaining = int(60 - (now - existing["sent_at"]))
        raise HTTPException(status_code=429, detail=f"请 {remaining} 秒后再试")

    code = str(random.randint(100000, 999999))
    _reset_codes[body.username] = {
        "code": code,
        "expires_at": now + 600,
        "sent_at": now,
        "user_id": user.id,
    }

    # 脱敏邮箱用于前端显示
    at_idx = email.find("@")
    masked_email = email[:3] + "***" + email[at_idx:] if at_idx > 3 else email

    html_body = (
        f"<h3>密码重置验证码</h3>"
        f"<p>您好，{user.username}：</p>"
        f"<p>您正在重置密码，请使用以下验证码（10 分钟内有效）：</p>"
        f"<p style='font-size:32px;letter-spacing:8px;font-weight:bold;text-align:center;padding:16px;background:#f5f5f5;border-radius:8px;color:#FF7A22;'>{code}</p>"
        f"<p>如非本人操作，请忽略此邮件。</p>"
        f"<hr><p style='color:gray;font-size:12px;'>AI Opinion Analytics</p>"
    )

    ok_result = send_email(
        to_address=email,
        subject="【AI Opinion Analytics】密码重置验证码",
        html_body=html_body,
    )

    if not ok_result:
        logger.error("发送验证码: 邮件发送失败 %s", email)
        raise HTTPException(status_code=502, detail="邮件发送失败，请稍后重试")

    logger.info('验证码已发送至 %s (user=%s)', email, user.username)
    return ok({"masked_email": masked_email}, "验证码已发送")


@router.post("/reset-password")
async def reset_password(
    body: VerifyResetCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    import time

    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="密码至少需要6位")

    if body.password != body.confirm_password:
        raise HTTPException(status_code=422, detail="两次密码不一致")

    record = _reset_codes.get(body.username)
    if not record:
        raise HTTPException(status_code=400, detail="请先获取验证码")

    now = time.time()
    if now > record["expires_at"]:
        _reset_codes.pop(body.username, None)
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")

    if record["code"] != body.code:
        raise HTTPException(status_code=400, detail="验证码不正确")

    result = await db.execute(select(User).where(User.id == record["user_id"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.password_hash = hash_password(body.password)
    await db.flush()
    _reset_codes.pop(body.username, None)

    logger.info('密码已重置: user=%s', user.username)
    return ok(None, "密码重置成功")

@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息（需携带有效 JWT）"""
    logger.info('用户"%s"获取个人信息', current_user.username)
    return ok(_user_to_frontend(current_user))
