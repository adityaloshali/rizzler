"""
Database connection and session management.
Uses async SQLAlchemy with PostgreSQL (Supabase).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from supabase import Client, create_client

from app.config import settings


# ===========================================
# SQLAlchemy Async Engine
# ===========================================

engine = create_async_engine(
    settings.async_database_url,
    echo=settings.debug,  # Log SQL in development
    pool_pre_ping=True,  # Verify connections before use
    pool_size=5,
    max_overflow=10,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI routes.
    Provides a database session and handles cleanup.
    
    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for use outside of FastAPI routes.
    
    Usage:
        async with get_db_context() as db:
            result = await db.execute(...)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ===========================================
# Supabase Client (for Auth & Storage)
# ===========================================

_supabase_client: Client | None = None


def get_supabase() -> Client:
    """
    Get Supabase client for Auth and Storage operations.
    Uses lazy initialization.
    """
    global _supabase_client

    if _supabase_client is None:
        if not settings.supabase_url or not settings.supabase_public_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_PUBLIC_KEY must be set in environment"
            )
        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_public_key,
        )

    return _supabase_client


def get_supabase_admin() -> Client:
    """
    Get Supabase client with secret key (admin access).
    Use sparingly - only for operations that require elevated permissions.
    """
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SECRET_KEY must be set"
        )
    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key,
    )


# ===========================================
# Database Initialization
# ===========================================

async def init_db() -> None:
    """
    Initialize database tables.
    Called on application startup.
    
    Note: In production, use Alembic migrations instead.
    """
    from app.models import Base

    async with engine.begin() as conn:
        # Create pgvector extension if not exists
        await conn.execute(
            "CREATE EXTENSION IF NOT EXISTS vector"  # type: ignore
        )
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close database connections.
    Called on application shutdown.
    """
    await engine.dispose()

