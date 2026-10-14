"""Settings parsing, derived URLs and production safety checks."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

STRONG = {
    "postgres_password": "pg-Str0ng!",
    "redis_password": "redis-Str0ng!",
    "rabbitmq_password": "rmq-Str0ng!",
    "minio_root_password": "minio-Str0ng!",
    "jwt_secret_key": "jwt-Str0ng-super-secret-key-32-chars!",
}


def test_database_url_uses_psycopg_and_encodes_special_characters(make_settings):
    settings = make_settings(
        postgres_user="app user",
        postgres_password="p@ss:w/rd#%",
        postgres_host="db",
        postgres_port=6543,
        postgres_db="disaster",
    )

    assert settings.database_url == (
        "postgresql+psycopg://app%20user:p%40ss%3Aw%2Frd%23%25@db:6543/disaster"
    )
    assert settings.database_url_for("disaster_test").endswith("@db:6543/disaster_test")


def test_redis_and_rabbitmq_urls(make_settings):
    settings = make_settings(
        redis_host="cache",
        redis_password="r/p",
        redis_db=2,
        rabbitmq_host="mq",
        rabbitmq_user="u",
        rabbitmq_password="p@",
        rabbitmq_vhost="disaster",
    )

    assert settings.redis_url == "redis://:r%2Fp@cache:6379/2"
    assert settings.rabbitmq_url == "amqp://u:p%40@mq:5672/disaster"


def test_minio_base_url_scheme_follows_secure_flag(make_settings):
    assert make_settings(minio_endpoint="s3:9000").minio_base_url == "http://s3:9000"
    assert (
        make_settings(minio_endpoint="s3:9000", minio_secure=True).minio_base_url
        == "https://s3:9000"
    )


def test_minio_endpoint_with_scheme_is_rejected(make_settings):
    with pytest.raises(ValidationError, match="without a scheme"):
        make_settings(minio_endpoint="http://minio:9000")


def test_cors_origins_parsed_from_comma_separated_env(monkeypatch, make_settings):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test ,")
    assert make_settings().cors_origins == ["http://a.test", "http://b.test"]


def test_log_level_is_case_insensitive(make_settings):
    assert make_settings(log_level="debug").log_level == "DEBUG"


def test_invalid_log_format_rejected(make_settings):
    with pytest.raises(ValidationError):
        make_settings(log_format="xml")


def test_secrets_are_masked_in_repr(make_settings):
    settings = make_settings(postgres_password="super-secret-value")
    assert "super-secret-value" not in repr(settings)
    assert "super-secret-value" not in str(settings.model_dump())


def test_production_refuses_placeholder_secrets(make_settings):
    with pytest.raises(ValidationError, match="placeholder secrets") as exc:
        make_settings(environment="production", **{**STRONG, "redis_password": "change-me-redis"})
    assert "redis_password" in str(exc.value)
    assert "postgres_password" not in str(exc.value)

    with pytest.raises(ValidationError, match="placeholder secrets") as exc:
        make_settings(
            environment="production",
            **{**STRONG, "jwt_secret_key": "change-me-jwt"},
        )
    assert "jwt_secret_key" in str(exc.value)


def test_production_accepts_real_secrets(make_settings):
    settings = make_settings(environment="production", **STRONG)
    assert settings.environment.value == "production"


def test_development_allows_placeholder_secrets(make_settings):
    assert make_settings(environment="development").postgres_password.get_secret_value()
