"""Pydantic schemas for user registration, authentication and profiles."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.users.models import UserRole


class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Full name")
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (minimum 8 characters)",
    )
    phone: str | None = Field(
        default=None,
        max_length=20,
        description="Optional contact phone number",
    )

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty or whitespace only")
        return cleaned

    @field_validator("email", mode="after")
    @classmethod
    def _lowercase_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Password")

    @field_validator("email", mode="after")
    @classmethod
    def _lowercase_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, description="JWT refresh token")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, description="JWT refresh token to revoke")


class MessageResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    phone: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime
