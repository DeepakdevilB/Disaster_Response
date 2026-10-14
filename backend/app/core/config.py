"""Application settings, loaded from environment variables (and an optional .env file).

Every setting has a matching UPPER_CASE environment variable, e.g. ``postgres_host`` <-
``POSTGRES_HOST``. Connection URLs are *derived* from the individual parts so that
passwords containing special characters are always URL-encoded correctly.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Repository root (…/backend/app/core/config.py -> repo root). Lets `uvicorn` and `pytest`
# pick up the shared root .env when run from backend/ on a developer machine.
_REPO_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"

PLACEHOLDER_SECRET_PREFIX = "change-me"  # noqa: S105


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT_ENV, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- application ----
    app_name: str = "disaster-response-api"
    app_version: str = "0.1.0"
    environment: Environment = Environment.DEVELOPMENT
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # ---- PostgreSQL ----
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "disaster"
    postgres_user: str = "disaster"
    postgres_password: SecretStr = SecretStr("change-me-postgres")
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=100)

    # ---- Redis ----
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: SecretStr = SecretStr("change-me-redis")
    redis_db: int = Field(default=0, ge=0, le=15)

    # ---- RabbitMQ ----
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "disaster"
    rabbitmq_password: SecretStr = SecretStr("change-me-rabbitmq")
    rabbitmq_vhost: str = "disaster"

    # ---- MinIO ----
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "disaster-minio"
    minio_root_password: SecretStr = SecretStr("change-me-minio")
    minio_secure: bool = False
    minio_bucket: str = "incident-media"

    # ---- health checks ----
    health_check_timeout_seconds: float = Field(default=2.0, gt=0, le=30)

    # ------------------------------------------------------------------ validators
    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("minio_endpoint")
    @classmethod
    def _endpoint_without_scheme(cls, value: str) -> str:
        if "://" in value:
            raise ValueError("MINIO_ENDPOINT must be host:port without a scheme")
        return value

    @model_validator(mode="after")
    def _no_placeholder_secrets_in_production(self) -> Settings:
        if self.environment is not Environment.PRODUCTION:
            return self
        placeholders = [
            name
            for name in (
                "postgres_password",
                "redis_password",
                "rabbitmq_password",
                "minio_root_password",
            )
            if getattr(self, name).get_secret_value().startswith(PLACEHOLDER_SECRET_PREFIX)
        ]
        if placeholders:
            raise ValueError(
                "Refusing to start in production with placeholder secrets: "
                + ", ".join(sorted(placeholders))
            )
        return self

    # ------------------------------------------------------------------ derived URLs
    @property
    def database_url(self) -> str:
        """SQLAlchemy URL using the psycopg 3 driver."""
        return self.database_url_for(self.postgres_db)

    def database_url_for(self, database: str) -> str:
        password = quote(self.postgres_password.get_secret_value(), safe="")
        user = quote(self.postgres_user, safe="")
        return (
            f"postgresql+psycopg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{quote(database, safe='')}"
        )

    @property
    def redis_url(self) -> str:
        password = quote(self.redis_password.get_secret_value(), safe="")
        return f"redis://:{password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def rabbitmq_url(self) -> str:
        user = quote(self.rabbitmq_user, safe="")
        password = quote(self.rabbitmq_password.get_secret_value(), safe="")
        vhost = quote(self.rabbitmq_vhost, safe="")
        return f"amqp://{user}:{password}@{self.rabbitmq_host}:{self.rabbitmq_port}/{vhost}"

    @property
    def minio_base_url(self) -> str:
        scheme = "https" if self.minio_secure else "http"
        return f"{scheme}://{self.minio_endpoint}"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance. Tests can call ``get_settings.cache_clear()``."""
    return Settings()
