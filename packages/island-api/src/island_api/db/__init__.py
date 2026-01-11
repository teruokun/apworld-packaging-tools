# SPDX-License-Identifier: MIT
"""Database module for Island repository."""

from typing import TYPE_CHECKING

from .audit import (
    AuditAction,
    create_audit_log,
    get_actor_audit_logs,
    get_package_audit_logs,
    get_recent_audit_logs,
    get_version_audit_logs,
    parse_audit_details,
)

if TYPE_CHECKING:
    from ..config import DatabaseConfig

__all__ = [
    "AuditAction",
    "create_audit_log",
    "get_actor_audit_logs",
    "get_package_audit_logs",
    "get_recent_audit_logs",
    "get_version_audit_logs",
    "parse_audit_details",
    "init_db",
    "close_db",
    "get_session",
]

# Database engine and session will be initialized at startup
_engine = None
_session_factory = None


async def init_db(config: "DatabaseConfig") -> None:
    """Initialize database connection.

    Args:
        config: Database configuration
    """
    global _engine, _session_factory

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    # Convert sync URL to async if needed
    url = config.url
    if url.startswith("sqlite:///"):
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://")

    _engine = create_async_engine(
        url,
        echo=config.echo,
        pool_size=config.pool_size if "sqlite" not in url else 1,
        max_overflow=config.max_overflow if "sqlite" not in url else 0,
    )

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables
    from .models import Base

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connection."""
    global _engine, _session_factory

    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def get_session():
    """Get database session for dependency injection."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized")

    async with _session_factory() as session:
        yield session
