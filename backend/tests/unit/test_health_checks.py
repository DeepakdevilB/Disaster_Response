"""Unit tests for the health-check runner and the real check factories (no services needed)."""

from __future__ import annotations

import pytest

from app.services.health import (
    default_checks,
    make_minio_check,
    make_rabbitmq_check,
    make_redis_check,
    run_checks,
)

# Port 1 on loopback: nothing listens there, so connections are refused immediately.
CLOSED = {"host": "127.0.0.1", "port": 1}


def test_run_checks_with_no_checks_returns_empty():
    assert run_checks({}, timeout_seconds=1) == {}


def test_run_checks_reports_exception_type_only():
    def failing() -> None:
        raise ValueError("secret detail")

    result = run_checks({"x": failing}, timeout_seconds=1)["x"]
    assert result.status == "error"
    assert result.error == "ValueError"


def test_default_checks_cover_all_backing_services(make_settings):
    assert set(default_checks(make_settings())) == {"postgres", "redis", "rabbitmq", "minio"}


@pytest.mark.parametrize(
    ("factory", "overrides"),
    [
        (make_redis_check, {"redis_host": CLOSED["host"], "redis_port": CLOSED["port"]}),
        (make_rabbitmq_check, {"rabbitmq_host": CLOSED["host"], "rabbitmq_port": CLOSED["port"]}),
        (make_minio_check, {"minio_endpoint": f"{CLOSED['host']}:{CLOSED['port']}"}),
    ],
    ids=["redis", "rabbitmq", "minio"],
)
def test_real_checks_fail_when_service_unreachable(make_settings, factory, overrides):
    settings = make_settings(health_check_timeout_seconds=1, **overrides)
    result = run_checks({"svc": factory(settings)}, timeout_seconds=3)["svc"]
    assert result.status == "error"
    assert result.error
