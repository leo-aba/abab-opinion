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
from backend.schemas.auth import LoginRequest, RegisterRequest
from backend.schemas.common import ok
from backend.service.auth_service import hash_password, verify_password, create_access_token

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


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息（需携带有效 JWT）"""
    logger.info('用户"%s"获取个人信息', current_user.username)
    return ok(_user_to_frontend(current_user))
