"""Password hashing and JWT token management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings


class TokenError(Exception):
    """Base exception for token issues."""


class TokenExpiredError(TokenError):
    """The token has expired."""


class TokenInvalidError(TokenError):
    """The token signature, format, or claims are invalid."""


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with a salt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that a plaintext password matches a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    role: str,
    email: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, str]:
    """Create a signed JWT refresh token with a unique jti identifier.

    Returns:
        tuple[str, str]: (token_string, jti_identifier)
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(days=settings.refresh_token_expire_days)
    )
    token_id = str(uuid.uuid4())

    payload: dict[str, Any] = {
        "sub": subject,
        "jti": token_id,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, token_id


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token's signature and expiration."""
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise TokenInvalidError("Invalid token") from exc
