"""SQLAlchemy 异步引擎 + Session + Base

引擎延迟到 FastAPI lifespan 启动时才创建，避免 uvicorn reload 子进程
在 conda 环境下找不到 asyncmy 驱动的问题。
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.config import DATABASE_URL

# 懒加载 — 只在 lifespan 中 init_db() 后才可用
_engine = None
_AsyncSessionLocal = None


def get_engine():
    """获取 SQLAlchemy 异步引擎（懒加载单例，仅首次调用时创建）"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            DATABASE_URL, pool_size=10, max_overflow=20, echo=False
        )
    return _engine


def get_sessionmaker():
    """获取异步 Session 工厂（懒加载单例，仅首次调用时创建）"""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _AsyncSessionLocal


async def init_db():
    """在 lifespan startup 中调用，确保引擎和连接池就绪"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """在 lifespan shutdown 中调用，释放连接池"""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


class Base(DeclarativeBase):
    pass


async def get_db():
    """每个请求注入一个数据库 session"""
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
