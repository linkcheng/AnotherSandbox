"""async SQLAlchemy engine + session。data-model.md §3。"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from orchestrator.core.config import get_settings

_settings = get_settings()
engine = create_async_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：提供事务边界内的 async session。"""
    async with SessionLocal() as session:
        yield session
