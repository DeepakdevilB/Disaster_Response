"""Shared pytest fixtures for unit tests (no external services needed)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.health import get_health_checks
from app.core.config import Settings
from app.main import create_app
from app.services.health import HealthCheck


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    """Build Settings that ignore any .env file, so tests are deterministic."""

    def factory(**overrides: Any) -> Settings:
        overrides.setdefault("environment", "test")
        return Settings(_env_file=None, **overrides)

    return factory


@pytest.fixture
def make_client(make_settings: Callable[..., Settings]) -> Iterator[Callable[..., TestClient]]:
    """Create a TestClient whose readiness checks are replaced by the given fakes."""
    clients: list[TestClient] = []

    def factory(
        checks: dict[str, HealthCheck] | None = None,
        configure: Callable[[FastAPI], None] | None = None,
        **settings_overrides: Any,
    ) -> TestClient:
        app = create_app(make_settings(**settings_overrides))
        if checks is not None:
            app.dependency_overrides[get_health_checks] = lambda: checks
        if configure is not None:
            configure(app)
        client = TestClient(app, raise_server_exceptions=False)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()
