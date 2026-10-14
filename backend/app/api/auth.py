"""Authentication router (register, login, refresh, logout)."""

from __future__ import annotations

import contextlib
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import TokenError
from app.db.session import get_db
from app.modules.users.schemas import (
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.modules.users.service import (
    AccountDisabledError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    authenticate_user,
    issue_tokens_for_user,
    refresh_access_token,
    register_user,
    revoke_refresh_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new citizen account",
)
def register(
    data: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    try:
        user = register_user(db, data)
        logger.info("new user registered", extra={"user_id": str(user.id), "role": user.role.value})
        return UserResponse.model_validate(user)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists",
        ) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive access and refresh tokens",
)
def login(
    data: UserLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        user = authenticate_user(db, email=data.email, password=data.password)
        logger.info("user authenticated", extra={"user_id": str(user.id), "role": user.role.value})
        return issue_tokens_for_user(user)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AccountDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        ) from exc


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and obtain fresh access token",
)
def refresh_token(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        return refresh_access_token(db, refresh_token=data.refresh_token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke refresh token",
)
def logout(
    data: LogoutRequest,
) -> MessageResponse:
    with contextlib.suppress(TokenError):
        revoke_refresh_token(data.refresh_token)
    return MessageResponse(message="Successfully logged out")
