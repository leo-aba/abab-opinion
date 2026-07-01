"""FastAPI 依赖注入 — JWT 鉴权"""

from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

from backend.config import JWT_SECRET, JWT_ALGORITHM
from backend.database import get_db


async def get_current_user(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    """从 Authorization header 中解析 JWT，返回当前用户。

    前端请求头格式: Authorization: Bearer <token>
    如果 token 无效或不存在，抛出 401。
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = authorization[7:]  # 截掉 "Bearer "

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="无效的 Token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 已过期或无效")

    # 延迟导入避免循环依赖
    from backend.models.user import User

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    return user
