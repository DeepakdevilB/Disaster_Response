"""Alembic migration environment.

Database URL resolution order:
1. ``config.attributes["database_url"]`` - set programmatically (used by the test suite);
2. application settings (``POSTGRES_*`` environment variables / .env).
"""

from __future__ import annotations

from geoalchemy2 import alembic_helpers
from sqlalchemy import create_engine, pool

from alembic import context
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.migration_utils import include_object
from app.db.registry import Base

config = context.config
settings = get_settings()

if config.attributes.get("configure_logging", True):
    configure_logging(level=settings.log_level, fmt=settings.log_format, service="alembic")

target_metadata = Base.metadata


def _database_url() -> str:
    return config.attributes.get("database_url") or settings.database_url


def _configure_kwargs() -> dict:
    return {
        "target_metadata": target_metadata,
        "include_object": include_object,
        "render_item": alembic_helpers.render_item,
        "compare_type": True,
        "compare_server_default": False,
    }


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing it (``alembic upgrade head --sql``)."""
    context.configure(
        url=_database_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_configure_kwargs(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, **_configure_kwargs())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
