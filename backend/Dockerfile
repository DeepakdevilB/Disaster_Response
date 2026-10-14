# syntax=docker/dockerfile:1
# Multi-stage image for the API (and later the Celery workers, which share this code base).
#   runtime : slim production image, non-root
#   test    : runtime + dev dependencies + tests (used by CI / `docker compose --profile test`)

ARG PYTHON_VERSION=3.11

# ---------------------------------------------------------------- builder: wheels only
FROM python:${PYTHON_VERSION}-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip wheel --wheel-dir /wheels ".[dev]"

# ---------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

# Install runtime deps only (no pytest/ruff in the production image); wheels are not kept.
RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels \
    pip install --no-index --find-links /wheels disaster-response-backend

COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app

USER app
EXPOSE 8000
# --proxy-headers so client IPs are correct behind Nginx (T-059).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-access-log"]

# ---------------------------------------------------------------- test
FROM runtime AS test
USER root
RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels \
    pip install --no-index --find-links /wheels "disaster-response-backend[dev]"
COPY --chown=app:app pyproject.toml ./
COPY --chown=app:app tests ./tests
USER app
CMD ["pytest", "--cov=app", "--cov-report=term-missing"]
