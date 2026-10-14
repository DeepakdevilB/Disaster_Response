"""FastAPI application factory.

Run locally:   uvicorn app.main:app --reload        (from backend/)
In Docker:     see backend/Dockerfile and docker-compose.yml
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
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

    # Inject the settings instance so Depends(get_settings) returns *this* settings,
    # not the lru_cache'd singleton (critical for testing with overridden settings).
    app.dependency_overrides[get_settings] = lambda: settings

    # Versioned business routers (auth, incidents, resources...) mount under /api/v1 from T-013.
    return app


app = create_app()
