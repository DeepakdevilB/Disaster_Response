"""Business logic for user registration, authentication, token rotation, and profile management."""

from __future__ import annotations

import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    TokenError,
    TokenInvalidError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.users.models import User, UserRole
from app.modules.users.schemas import TokenResponse, UserRegisterRequest
from app.services.token_blacklist import get_token_blacklist


class AuthError(Exception):
    """Base error for authentication failures."""


class EmailAlreadyExistsError(AuthError):
    """Attempted to register with an email that is already in use."""


class InvalidCredentialsError(AuthError):
    """Invalid email or password."""


class AccountDisabledError(AuthError):
    """The account has been deactivated."""


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """Fetch a user by their unique UUID."""
    return db.scalar(select(User).where(User.id == user_id))


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by lowercased email."""
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def register_user(db: Session, data: UserRegisterRequest) -> User:
    """Register a new citizen user.

    Raises:
        EmailAlreadyExistsError: If the email is already registered.
    """
    clean_email = str(data.email).strip().lower()
    existing = get_user_by_email(db, clean_email)
    if existing is not None:
        raise EmailAlreadyExistsError(f"Email {clean_email} is already registered")

    user = User(
        name=data.name.strip(),
        email=clean_email,
        phone=data.phone.strip() if data.phone else None,
        password_hash=hash_password(data.password),
        role=UserRole.CITIZEN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# Precomputed bcrypt hash used to equalize response timing when user is not found
_DUMMY_BCRYPT_HASH = "$2b$12$e8pA7Lq.1Kqm1r6a6E0.7u4s9U/DqJ7oH2c1eQ9/b6gE5jQ7y5e2K"


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Validate credentials and return user if active.

    Raises:
        InvalidCredentialsError: On incorrect email or password.
        AccountDisabledError: If user exists but is deactivated.
    """
    user = get_user_by_email(db, email)
    if user is None:
        # Protect against user-enumeration timing attacks with a dummy password check
        verify_password("dummy-password", _DUMMY_BCRYPT_HASH)
        raise InvalidCredentialsError("Invalid email or password")

    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password")

    if not user.is_active:
        raise AccountDisabledError("User account is inactive")

    return user


def issue_tokens_for_user(user: User) -> TokenResponse:
    """Generate a fresh access token and refresh token for a user."""
    settings = get_settings()
    access_token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
        email=user.email,
    )
    refresh_token, _ = create_refresh_token(subject=str(user.id))
    expires_in = settings.access_token_expire_minutes * 60

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",  # noqa: S106
        expires_in=expires_in,
    )


def refresh_access_token(db: Session, refresh_token: str) -> TokenResponse:
    """Rotate an existing refresh token and issue a fresh access token.

    Raises:
        TokenInvalidError: If the token is invalid, expired, wrong type, revoked, or user inactive.
    """
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise TokenInvalidError("Invalid token type: expected refresh token")

    jti = payload.get("jti")
    if not jti:
        raise TokenInvalidError("Missing token identifier")

    blacklist = get_token_blacklist()
    if blacklist.is_revoked(jti):
        raise TokenInvalidError("Refresh token has been revoked")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError) as exc:
        raise TokenInvalidError("Invalid subject claim in token") from exc

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise TokenInvalidError("User not found or account is inactive")

    # Invalidate the old refresh token (refresh token rotation)
    exp = payload.get("exp", int(time.time()))
    remaining_seconds = max(1, exp - int(time.time()))
    blacklist.revoke(jti, remaining_seconds)

    # Issue a fresh pair
    return issue_tokens_for_user(user)


def revoke_refresh_token(refresh_token: str) -> None:
    """Blacklist a refresh token so it cannot be used again.

    Raises:
        TokenError: If the token format or signature is invalid.
    """
    try:
        payload = decode_token(refresh_token)
    except TokenError:
        # If token is already expired or malformed, nothing to revoke
        return

    if payload.get("type") != "refresh":
        raise TokenInvalidError("Invalid token type: expected refresh token")

    jti = payload.get("jti")
    if jti:
        exp = payload.get("exp", int(time.time()))
        remaining_seconds = max(1, exp - int(time.time()))
        get_token_blacklist().revoke(jti, remaining_seconds)
