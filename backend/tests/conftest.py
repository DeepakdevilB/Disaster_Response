"""Shared pytest fixtures for unit tests (no external services needed)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.health import get_health_checks
from app.core.config import Settings
from app.db.session import get_db
from app.main import create_app
from app.services.health import HealthCheck


@pytest.fixture
def db_session() -> Iterator[Session]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.db.registry  # noqa: F401
    from app.db.base import Base

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    """Build Settings that ignore any .env file, so tests are deterministic."""

    def factory(**overrides: Any) -> Settings:
        overrides.setdefault("environment", "test")
        return Settings(_env_file=None, **overrides)

    return factory


@pytest.fixture
def make_client(make_settings: Callable[..., Settings]) -> Iterator[Callable[..., TestClient]]:
    """Create a TestClient whose readiness checks and db session can be replaced."""
    clients: list[TestClient] = []

    def factory(
        checks: dict[str, HealthCheck] | None = None,
        db: Session | None = None,
        configure: Callable[[FastAPI], None] | None = None,
        **settings_overrides: Any,
    ) -> TestClient:
        app = create_app(make_settings(**settings_overrides))
        if checks is not None:
            app.dependency_overrides[get_health_checks] = lambda: checks
        if db is not None:
            app.dependency_overrides[get_db] = lambda: db
        if configure is not None:
            configure(app)
        client = TestClient(app, raise_server_exceptions=False)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()
