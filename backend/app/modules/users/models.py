"""Users and roles."""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, CheckConstraint, Index, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.types import UUIDPrimaryKeyMixin, pg_enum


class UserRole(enum.StrEnum):
    CITIZEN = "citizen"
    AUTHORITY = "authority"
    RESCUE = "rescue"
    ADMIN = "admin"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # Emails are normalised to lower case by the application; the DB enforces it so the
        # plain UNIQUE constraint is effectively case-insensitive.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        Index("ix_users_role", "role"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"),
        nullable=False,
        default=UserRole.CITIZEN,
        server_default=UserRole.CITIZEN.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )

    def __repr__(self) -> str:  # never include password_hash
        return f"<User id={self.id} role={self.role}>"
