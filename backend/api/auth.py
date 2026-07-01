"""认证接口 — /api/auth/*

前端调用:
  POST /api/auth/login     → api.login(username, password, remember)
  POST /api/auth/register  → api.register(username, email, password)
"""

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
        "display_name": user.username,           # 后续可以单独存 display_name
        "role": _ROLE_LABELS.get(user.role.value if hasattr(user.role, "value") else user.role, user.role),
        "avatar_initial": user.username[0].upper() if user.username else "U",
        "email": user.email,
    }


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    token = create_access_token(user.id)
    return ok({
        "token": token,
        "user": _user_to_frontend(user),
    })


@router.post("/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    if body.password != body.confirm_password:
        raise HTTPException(status_code=422, detail="两次密码不一致")
    if len(body.username) < 3:
        raise HTTPException(status_code=422, detail="用户名至少需要3位")
    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="密码至少需要6位")

    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已存在")

    if body.email:
        existing_email = await db.execute(select(User).where(User.email == body.email))
        if existing_email.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="邮箱已被注册")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()

    return ok(None, "注册成功")


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return ok(_user_to_frontend(current_user))
