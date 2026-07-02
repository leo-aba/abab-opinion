"""用户接口 — /api/user/*

前端调用:
  GET /api/user/profile  → 获取当前用户信息（侧边栏用）
"""

import logging

from fastapi import APIRouter, Depends

from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.common import ok

logger = logging.getLogger("user")

router = APIRouter(prefix="/api/user", tags=["用户"])

# DB 角色 → 前端显示名称（与 auth.py 保持一致）
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
        "role": _ROLE_LABELS.get(
            user.role.value if hasattr(user.role, "value") else user.role, user.role
        ),
        "avatar_initial": user.username[0].upper() if user.username else "U",
        "email": user.email,
    }


@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    """获取当前用户信息（侧边栏头像、姓名、角色）"""
    logger.info('用户"%s"获取个人资料', current_user.username)
    return ok(_user_to_frontend(current_user))
