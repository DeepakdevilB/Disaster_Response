"""Unit tests for cryptographic functions: password hashing, verification, and JWTs."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.security import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing_and_verification():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$2b$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False


def test_verify_password_handles_malformed_hash():
    assert verify_password("secret", "not-a-valid-bcrypt-hash") is False
    assert verify_password("secret", "") is False


def test_create_and_decode_access_token(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-chars-long!")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")

    token = create_access_token(
        subject="00000000-0000-0000-0000-000000000001",
        role="citizen",
        email="citizen@example.com",
    )
    payload = decode_token(token)

    assert payload["sub"] == "00000000-0000-0000-0000-000000000001"
    assert payload["role"] == "citizen"
    assert payload["email"] == "citizen@example.com"
    assert payload["type"] == "access"
    assert payload["exp"] - payload["iat"] == 15 * 60
    get_settings.cache_clear()


def test_expired_token_raises_token_expired_error(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-chars-long!")

    token = create_access_token(
        subject="user-1",
        role="citizen",
        email="test@example.com",
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(TokenExpiredError, match="Token has expired"):
        decode_token(token)
    get_settings.cache_clear()


def test_token_with_invalid_signature_raises_token_invalid_error(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "correct-secret-key-32-characters-minimum!")
    token = create_access_token(subject="user-1", role="citizen", email="test@example.com")

    # Change secret in environment and clear cache so decode_token uses the new secret
    monkeypatch.setenv("JWT_SECRET_KEY", "different-secret-key-32-characters-minimum!")
    get_settings.cache_clear()

    with pytest.raises(TokenInvalidError, match="Invalid token"):
        decode_token(token)
    get_settings.cache_clear()


def test_tampered_token_raises_token_invalid_error(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-chars-long!")
    token = create_access_token(subject="user-1", role="citizen", email="test@example.com")
    tampered = token[:-4] + "xxxx"

    with pytest.raises(TokenInvalidError, match="Invalid token"):
        decode_token(tampered)


def test_create_and_decode_refresh_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-chars-long!")
    monkeypatch.setenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")

    token, jti = create_refresh_token(subject="user-1")
    assert jti
    assert isinstance(jti, str)

    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["jti"] == jti
    assert payload["type"] == "refresh"
    assert payload["exp"] - payload["iat"] == 7 * 86400
