"""Async engine and session management.

Engine and sessionmaker are created lazily, on first use, and cached at
module level — not at import time. This matters concretely: `pytest`
imports this module indirectly through `overture.main`, and if engine
creation happened eagerly at import time, every test run would try to
open a database connection whether or not the test actually needs one.
Session 2's tests don't touch the database at all; they'd break for a
reason that has nothing to do with what they're testing.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from overture.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, echo=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency. Not wired into any route yet — see flow.md
    open threads. Exists now so session 3's routes can depend on it
    without a detour back through this file.
    """
    async with get_sessionmaker()() as session:
        yield session
