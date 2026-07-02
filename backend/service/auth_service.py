"""认证服务 — 密码哈希 + JWT 生成 + 密码验证"""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from backend.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_SECONDS


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希，返回哈希后的字符串"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """验证明文密码是否与 bcrypt 哈希匹配"""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    """签发 JWT 访问令牌，包含 user_id 和过期时间"""
    expire = datetime.now(timezone.utc) + timedelta(seconds=JWT_EXPIRE_SECONDS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
