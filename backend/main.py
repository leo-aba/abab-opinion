"""AI Opinion Analytics — FastAPI 应用入口

启动:  uvicorn backend.main:app --reload --port 8000
前端:  http://localhost:8000/login.html
文档:  http://localhost:8000/docs
"""

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.config import CORS_ORIGINS, BASE_DIR
from backend.database import init_db, close_db

# ---------- 日志配置 ----------
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库并注册关闭回调"""
    logger.info("正在启动服务...")
    await init_db()
    logger.info("数据库初始化完成")
    yield
    await close_db()
    logger.info("数据库连接池已释放")


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


# ---------- 请求日志中间件 ----------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录每个请求的方法、路径和响应状态"""
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    logger.debug("%s %s → %d (%.1fms)", request.method, request.url.path, response.status_code, elapsed)
    return response


# ---------- 统一异常处理 ----------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic 请求校验失败 → 422，提取第一条错误消息"""
    errors = exc.errors()
    first_msg = errors[0]["msg"] if errors else "请求参数校验失败"
    logger.warning("422 校验失败 | %s %s — %s", request.method, request.url.path, first_msg)
    return JSONResponse(
        status_code=422,
        content={"code": 422, "message": first_msg, "data": None},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """手动抛出的 HTTPException（如 401/403/409/422）"""
    logger.warning("HTTP %d | %s %s — %s", exc.status_code, request.method, request.url.path, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "data": None},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """未预料到的异常 → 500"""
    logger.error("未处理异常 | %s %s — %s", request.method, request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误", "data": None},
    )


# ---------- 健康检查 ----------
@app.get("/health")
async def health():
    """健康检查端点 — 供 Docker / K8s 探活使用"""
    return {"status": "ok"}


@app.get("/debug/routes")
async def debug_routes():
    """调试: 查看所有注册的路由"""
    from fastapi.routing import _IncludedRouter
    from starlette.routing import Mount
    info = []
    for i, route in enumerate(app.router.routes):
        rtype = type(route).__name__
        entry = {"index": i, "type": rtype}
        if hasattr(route, 'path'):
            entry["path"] = route.path
        if hasattr(route, 'name'):
            entry["name"] = route.name
        if hasattr(route, 'methods'):
            entry["methods"] = sorted(route.methods) if route.methods else []
        if isinstance(route, _IncludedRouter):
            sub = []
            for sr in route.original_router.routes:
                sub.append({"path": sr.path, "methods": sorted(sr.methods) if hasattr(sr, 'methods') and sr.methods else []})
            entry["sub_routes"] = sub
        info.append(entry)
    return {"routes": info}


@app.get("/debug/ping")
async def debug_ping(path: str = ""):
    """调试: 测试特定路径的路由匹配"""
    from starlette.routing import Match, get_route_path
    from fastapi.routing import _IncludedRouter
    from starlette.datastructures import URL
    # Create a mock scope
    scope = {
        "type": "http",
        "path": path or "/api/videos/search?query=BV1",
        "method": "GET",
        "scheme": "http",
        "server": ("localhost", 8000),
        "headers": [],
        "query_string": b"",
        "root_path": "",
        "path_params": {},
        "app": app,
    }
    results = []
    for i, route in enumerate(app.router.routes):
        try:
            match, child_scope = route.matches(scope)
            results.append({
                "index": i,
                "type": type(route).__name__,
                "path": getattr(route, 'path', ''),
                "match": str(match),
            })
        except Exception as e:
            results.append({
                "index": i,
                "type": type(route).__name__,
                "path": getattr(route, 'path', ''),
                "match": f"ERROR: {e}",
            })
    return {"results": results}


# ---------- 路由（API 在前，静态文件在后，避免路由冲突） ----------
from backend.api.auth import router as auth_router
from backend.api.user import router as user_router
from backend.api.videos import router as videos_router
from backend.api.analysis import router as analysis_router
from backend.api.settings import router as settings_router
from backend.api.dashboard import router as dashboard_router

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(videos_router)
app.include_router(analysis_router)
app.include_router(settings_router)
app.include_router(dashboard_router)

# 强制解析 _IncludedRouter 的候选路由，避免延迟解析问题
app.openapi()
logger.info("已注册 %d 个路由，OpenAPI 包含 %d 个路径",
             len(app.router.routes), len(app.openapi_schema.get("paths", {})))


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
        resp = FileResponse(safe_path)
        # 开发阶段禁用缓存，方便修改 JS/CSS 后即时生效
        if safe_path.endswith(('.js', '.css', '.html')):
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return resp

    # 2) 目录 → index.html（如 /example/ → /example/index.html）
    if os.path.isdir(safe_path):
        index_path = os.path.join(safe_path, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)

    # 3) 找不到 → 404
    raise HTTPException(status_code=404, detail="页面不存在")
