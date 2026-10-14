"""Liveness and readiness endpoints.

* ``GET /health``        - liveness: the process is up. No I/O, always fast. Used by Docker.
* ``GET /health/ready``  - readiness: all backing services reachable. 503 if any fails.

These are infrastructure endpoints (not under ``/api/v1``) and are expected to be reachable
only from inside the deployment network once Nginx is in place (T-059).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.services.health import HealthCheck, default_checks, run_checks

router = APIRouter(tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str


class CheckResultOut(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: float
    error: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    checks: dict[str, CheckResultOut]


def get_health_checks(settings: Settings = Depends(get_settings)) -> dict[str, HealthCheck]:
    """Dependency so tests can swap real checks for fakes via ``app.dependency_overrides``."""
    return default_checks(settings)


@router.get("/health", response_model=LivenessResponse, summary="Liveness probe")
def health(settings: Settings = Depends(get_settings)) -> LivenessResponse:
    return LivenessResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment.value,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe (checks Postgres, Redis, RabbitMQ, MinIO)",
    responses={503: {"model": ReadinessResponse, "description": "A dependency is unavailable"}},
)
def readiness(
    response: Response,
    settings: Settings = Depends(get_settings),
    checks: dict[str, HealthCheck] = Depends(get_health_checks),
) -> ReadinessResponse:
    results = run_checks(checks, timeout_seconds=settings.health_check_timeout_seconds)
    healthy = all(result.status == "ok" for result in results.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ok" if healthy else "unavailable",
        checks={
            name: CheckResultOut(status=r.status, latency_ms=r.latency_ms, error=r.error)
            for name, r in results.items()
        },
    )
