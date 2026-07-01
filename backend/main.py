"""AI Opinion Analytics — FastAPI 应用入口

启动:  uvicorn backend.main:app --reload --port 8000
前端:  http://localhost:8000/login.html
文档:  http://localhost:8000/docs
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.config import CORS_ORIGINS, BASE_DIR
from backend.database import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时创建表（表已存在则跳过），关闭时释放连接池"""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="AI Opinion Analytics API",
    description="AI 驱动的视频评论分析平台",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 统一异常处理 ----------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "message": exc.detail, "data": None},
        )
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": str(exc) or "服务器内部错误", "data": None},
    )


# ---------- 健康检查 ----------
@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------- 路由（API 在前，静态文件在后，避免路由冲突） ----------
from backend.api.auth import router as auth_router

app.include_router(auth_router)


# ---------- 托管前端静态文件 ----------
# BASE_DIR = 项目根目录 (ababOpinion/)，frontend 在 BASE_DIR/frontend/
frontend_dir = str(BASE_DIR / "frontend")

# css / js / logo.png 等资源
app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
app.mount("/js",  StaticFiles(directory=os.path.join(frontend_dir, "js")),  name="js")

# 静态资源托管 — 使用 catch-all 路由替代 app.mount("/")
# 重要: 路由注册顺序保证 API 优先匹配，GET 兜底才走这里

@app.get("/")
async def root():
    """根路径重定向到登录页"""
    return RedirectResponse(url="/login.html")


@app.get("/{filename:path}")
async def serve_frontend(filename: str):
    """托管前端静态资源（HTML、图片等），API 路由已注册在前优先匹配"""
    # 防止路径遍历攻击
    safe_path = os.path.normpath(os.path.join(frontend_dir, filename))
    if not safe_path.startswith(frontend_dir):
        raise HTTPException(status_code=404, detail="页面不存在")

    # 1) 精确文件匹配
    if os.path.isfile(safe_path):
        return FileResponse(safe_path)

    # 2) 目录 → index.html（如 /example/ → /example/index.html）
    if os.path.isdir(safe_path):
        index_path = os.path.join(safe_path, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)

    # 3) 找不到 → 404
    raise HTTPException(status_code=404, detail="页面不存在")
