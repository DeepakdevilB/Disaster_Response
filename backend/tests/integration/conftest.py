"""Fixtures for integration tests against a real PostgreSQL (PostGIS + pgvector).

A throw-away database ``<POSTGRES_DB>_test`` is created on the configured server, migrated with
Alembic, and dropped at the end of the session. If Postgres is unreachable the tests are
skipped - unless ``REQUIRE_INTEGRATION=1`` (set in CI and in the compose test runner), in which
case they fail loudly so a broken database can never produce a falsely green build.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from alembic import command
from alembic.config import Config
from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    here = Path(__file__).parent
    for item in items:
        if here in Path(item.fspath).parents:
            item.add_marker(pytest.mark.integration)


def _admin_conninfo(dbname: str) -> dict[str, object]:
    s = get_settings()
    return {
        "host": s.postgres_host,
        "port": s.postgres_port,
        "user": s.postgres_user,
        "password": s.postgres_password.get_secret_value(),
        "dbname": dbname,
        "connect_timeout": 3,
        "autocommit": True,
    }


def _recreate_database(name: str) -> None:
    with psycopg.connect(**_admin_conninfo("postgres")) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def _drop_database(name: str) -> None:
    with psycopg.connect(**_admin_conninfo("postgres")) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )


@pytest.fixture(scope="session")
def test_database_url() -> Iterator[str]:
    settings = get_settings()
    name = f"{settings.postgres_db}_test"
    try:
        _recreate_database(name)
    except psycopg.OperationalError as exc:
        message = (
            f"PostgreSQL not reachable at {settings.postgres_host}:{settings.postgres_port} "
            f"({type(exc).__name__}). Start it with `docker compose up -d postgres`."
        )
        if os.getenv("REQUIRE_INTEGRATION") == "1":
            pytest.fail(message)
        pytest.skip(message)
    yield settings.database_url_for(name)
    _drop_database(name)


@pytest.fixture(scope="session")
def alembic_config(test_database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["database_url"] = test_database_url
    config.attributes["configure_logging"] = False
    return config


@pytest.fixture(scope="session")
def engine(alembic_config: Config, test_database_url: str) -> Iterator[Engine]:
    command.upgrade(alembic_config, "head")
    eng = create_engine(test_database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back after each test (tests stay independent).

    Code under test may call ``commit()``; it only releases a SAVEPOINT inside the outer
    transaction, which is rolled back at the end.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
