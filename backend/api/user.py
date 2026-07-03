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


def _calc_credits_cost(analysis_mode: str, comment_count: int) -> tuple[int, str]:
    """根据分析模式和评论数量计算预估积分消耗。

    阶梯定价（normal 模式基准）：
      0 条         → 0
      1–100 条     → 1 积分/条
      101–500 条   → 0.8 积分/条
      500+ 条      → 0.6 积分/条
    tracking 模式在阶梯结果上 ×0.64，单位变为"积分/小时"。
    """
    if comment_count <= 0:
        base_cost = 0
    elif comment_count <= 100:
        base_cost = comment_count
    elif comment_count <= 500:
        base_cost = int(comment_count * 0.8)
    else:
        base_cost = int(comment_count * 0.6)

    if analysis_mode == "tracking":
        return int(base_cost * 0.64), "积分/小时"
    else:
        return base_cost, "积分"


@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    """获取当前用户信息（侧边栏头像、姓名、角色）"""
    logger.info('用户"%s"获取个人资料', current_user.username)
    return ok(_user_to_frontend(current_user))


@router.get("/credits")
async def get_credits(
    analysis_mode: str = "normal",
    comment_count: int = 0,
    current_user: User = Depends(get_current_user),
):
    """查询当前用户积分余额和预估消耗"""
    estimated_cost, cost_unit = _calc_credits_cost(analysis_mode, comment_count)
    available = current_user.credits or 0

    logger.info(
        '用户"%s"查询积分 — mode=%s count=%d → cost=%d available=%d',
        current_user.username, analysis_mode, comment_count, estimated_cost, available,
    )
    return ok({
        "available": available,
        "estimated_cost": estimated_cost,
        "cost_unit": cost_unit,
        "can_afford": available >= estimated_cost,
    })
