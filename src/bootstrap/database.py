"""Database session dependency."""

from functools import lru_cache
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.config import get_settings


_engine = None
_async_session_factory = None


def get_engine():
    """Get or create the async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        from sqlalchemy.ext.asyncio import create_async_engine

        _engine = create_async_engine(settings.database_url)
    return _engine


def get_session_factory():
    """Get or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        _async_session_factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_factory


async def dispose_engine():
    """Dispose the engine."""
    global _engine, _async_session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


def get_db():
    """Dependency to get database session."""
    return get_session_factory()()


async def init_db():
    """Initialize database engine and session factory."""
    get_engine()
    get_session_factory()
