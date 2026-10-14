"""FastAPI application factory.

Run locally:   uvicorn app.main:app --reload        (from backend/)
In Docker:     see backend/Dockerfile and docker-compose.yml
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.incidents import router as incidents_router
from app.api.users import router as users_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format, service=settings.app_name)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "application startup",
            extra={"environment": settings.environment.value, "version": settings.app_version},
        )
        yield
        logger.info("application shutdown")

    app = FastAPI(
        title="Disaster Response API",
        version=settings.app_version,
        description="Intelligent Disaster Response & Emergency Coordination Platform",
        lifespan=lifespan,
    )

    # Middleware order: the last added runs first. Request context wraps everything, so even
    # CORS preflight responses get a request id and an access-log line.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER, "Idempotency-Key"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        # Log the full traceback server-side; never leak internals to the client.
        logger.exception("unhandled exception", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(health_router)

    # Versioned business routers (auth, incidents, resources...) mount under /api/v1
    api_v1_router = APIRouter(prefix="/api/v1")
    api_v1_router.include_router(auth_router)
    api_v1_router.include_router(users_router)
    api_v1_router.include_router(admin_router)
    api_v1_router.include_router(incidents_router)
    app.include_router(api_v1_router)

    # Inject the settings instance so Depends(get_settings) returns *this* settings,
    # not the lru_cache'd singleton (critical for testing with overridden settings).
    app.dependency_overrides[get_settings] = lambda: settings

    return app


app = create_app()
