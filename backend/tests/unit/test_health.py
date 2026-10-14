"""Liveness/readiness endpoints, request-id propagation and error handling."""

from __future__ import annotations

import time

from fastapi import FastAPI


def _ok() -> None:
    return None


def _boom() -> None:
    raise ConnectionRefusedError("connection refused to secret-host:5432 password=hunter2")


def test_liveness_returns_ok_and_service_info(make_client):
    client = make_client(app_name="test-api")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "test-api",
        "version": "0.1.0",
        "environment": "test",
    }


def test_liveness_does_not_touch_dependencies(make_client):
    # Liveness must stay green even when every dependency is down.
    client = make_client(checks={"postgres": _boom, "redis": _boom})
    assert client.get("/health").status_code == 200


def test_readiness_ok_when_all_checks_pass(make_client):
    client = make_client(checks={"postgres": _ok, "redis": _ok, "rabbitmq": _ok, "minio": _ok})

    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["checks"]) == {"postgres", "redis", "rabbitmq", "minio"}
    assert all(check["status"] == "ok" for check in body["checks"].values())
    assert all(check["latency_ms"] >= 0 for check in body["checks"].values())


def test_readiness_503_when_a_check_fails_and_hides_error_details(make_client):
    client = make_client(checks={"postgres": _boom, "redis": _ok})

    response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["postgres"] == {
        "status": "error",
        "latency_ms": body["checks"]["postgres"]["latency_ms"],
        "error": "ConnectionRefusedError",
    }
    assert body["checks"]["redis"]["status"] == "ok"
    # The exception message (with host/password) must never reach the client.
    assert "hunter2" not in response.text
    assert "secret-host" not in response.text


def test_readiness_times_out_slow_checks(make_client):
    def slow() -> None:
        time.sleep(2)

    client = make_client(checks={"slow": slow, "fast": _ok}, health_check_timeout_seconds=0.2)

    started = time.perf_counter()
    response = client.get("/health/ready")
    elapsed = time.perf_counter() - started

    assert response.status_code == 503
    assert response.json()["checks"]["slow"]["error"] == "Timeout"
    assert response.json()["checks"]["fast"]["status"] == "ok"
    assert elapsed < 1.5, "readiness must not wait for a hung dependency"


def test_request_id_generated_when_missing(make_client):
    response = make_client().get("/health")
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32
    assert all(c in "0123456789abcdef" for c in request_id)


def test_valid_request_id_is_propagated(make_client):
    response = make_client().get("/health", headers={"X-Request-ID": "trace-abc.123_x"})
    assert response.headers["X-Request-ID"] == "trace-abc.123_x"


def test_unsafe_request_id_is_replaced(make_client):
    for bad in ("has spaces", "x" * 65, 'quote"inject'):
        response = make_client().get("/health", headers={"X-Request-ID": bad})
        assert response.headers["X-Request-ID"] != bad


def test_unhandled_exception_returns_generic_500(make_client):
    def add_failing_route(app: FastAPI) -> None:
        @app.get("/boom")
        def boom() -> None:
            raise RuntimeError("internal detail that must not leak")

    response = make_client(configure=add_failing_route).get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "internal detail" not in response.text


def test_cors_preflight_allows_configured_origin(make_client):
    client = make_client(cors_origins="http://localhost:5173")

    response = client.options(
        "/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unknown_origin(make_client):
    client = make_client(cors_origins="http://localhost:5173")

    response = client.options(
        "/health",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_openapi_schema_lists_health_routes(make_client):
    paths = make_client().get("/openapi.json").json()["paths"]
    assert "/health" in paths
    assert "/health/ready" in paths
