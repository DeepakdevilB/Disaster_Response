"""Dependency health checks used by the readiness endpoint.

Each check is a zero-argument callable that raises on failure. They run concurrently in a
thread pool, each bounded by a timeout, so one slow dependency cannot hang the endpoint.
Error *types* are reported, never error messages (which could contain hostnames/credentials).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Literal

import httpx
import redis
from kombu import Connection
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import get_engine

logger = logging.getLogger(__name__)

HealthCheck = Callable[[], None]
CheckStatus = Literal["ok", "error"]


@dataclass(frozen=True, slots=True)
class CheckResult:
    status: CheckStatus
    latency_ms: float
    error: str | None = None


def check_postgres() -> None:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))


def make_redis_check(settings: Settings) -> HealthCheck:
    def check() -> None:
        timeout = settings.health_check_timeout_seconds
        client = redis.Redis.from_url(
            settings.redis_url, socket_connect_timeout=timeout, socket_timeout=timeout
        )
        try:
            if not client.ping():
                raise ConnectionError("Redis PING failed")
        finally:
            client.close()

    return check


def make_rabbitmq_check(settings: Settings) -> HealthCheck:
    def check() -> None:
        # A full AMQP handshake: proves the broker is up AND our credentials/vhost are valid.
        with Connection(
            settings.rabbitmq_url, connect_timeout=settings.health_check_timeout_seconds
        ) as conn:
            conn.connect()

    return check


def make_minio_check(settings: Settings) -> HealthCheck:
    def check() -> None:
        response = httpx.get(
            f"{settings.minio_base_url}/minio/health/live",
            timeout=settings.health_check_timeout_seconds,
        )
        response.raise_for_status()

    return check


def default_checks(settings: Settings) -> dict[str, HealthCheck]:
    return {
        "postgres": check_postgres,
        "redis": make_redis_check(settings),
        "rabbitmq": make_rabbitmq_check(settings),
        "minio": make_minio_check(settings),
    }


def run_checks(checks: Mapping[str, HealthCheck], timeout_seconds: float) -> dict[str, CheckResult]:
    """Run all checks concurrently; a check that exceeds ``timeout_seconds`` counts as failed."""
    if not checks:
        return {}

    def timed(check: HealthCheck) -> float:
        start = time.perf_counter()
        check()
        return (time.perf_counter() - start) * 1000

    results: dict[str, CheckResult] = {}
    # Not using a `with` block: its shutdown would wait for a hung check and defeat the timeout.
    pool = ThreadPoolExecutor(max_workers=len(checks), thread_name_prefix="health")
    try:
        futures = {
            name: (pool.submit(timed, check), time.perf_counter()) for name, check in checks.items()
        }
        deadline = time.perf_counter() + timeout_seconds
        for name, (future, started) in futures.items():
            try:
                latency = future.result(timeout=max(0.0, deadline - time.perf_counter()))
                results[name] = CheckResult(status="ok", latency_ms=round(latency, 2))
            except FutureTimeout:
                results[name] = _failure(name, started, "Timeout")
            except Exception as exc:
                results[name] = _failure(name, started, type(exc).__name__)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return results


def _failure(name: str, started: float, error: str) -> CheckResult:
    latency = round((time.perf_counter() - started) * 1000, 2)
    logger.warning("health check failed", extra={"check": name, "error": error})
    return CheckResult(status="error", latency_ms=latency, error=error)
