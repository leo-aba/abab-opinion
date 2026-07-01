"""统一响应格式 — 所有接口都用 ok() / err() 包装"""

from typing import Any


def ok(data: Any = None, message: str = "success") -> dict:
    """成功响应"""
    return {"code": 0, "message": message, "data": data}


def err(message: str, code: int = 1) -> dict:
    """错误响应"""
    return {"code": code, "message": message, "data": None}
