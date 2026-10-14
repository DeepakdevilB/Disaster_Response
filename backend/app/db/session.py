"""Engine and session management (synchronous SQLAlchemy 2 + psycopg 3).

Sync was chosen deliberately (see docs/adr/0002-sync-sqlalchemy.md): the same session code is
reused by Celery workers, and FastAPI runs sync endpoints in a thread pool.
The engine is created lazily so importing the app never opens a DB connection.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # transparently replace connections dropped by Postgres restarts
        pool_recycle=1800,
        connect_args={"connect_timeout": 5, "application_name": settings.app_name},
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed after the request."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
