"""Admin user management endpoints."""

from __future__ import annotations

import logging
import uuid
from typing import Generic, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rbac import require_admin
from app.db.session import get_db
from app.modules.users.models import User, UserRole
from app.modules.users.schemas import UserResponse
from app.modules.users.service import get_user_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


class UpdateUserRoleRequest(BaseModel):
    role: UserRole = Field(..., description="New role for the user")


class UpdateUserStatusRequest(BaseModel):
    is_active: bool = Field(..., description="Active status")


@router.get(
    "/users",
    response_model=PaginatedResponse[UserResponse],
    summary="List users (Admin only)",
)
def list_users(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    role: UserRole | None = Query(default=None),
    db: Session = Depends(get_db),
) -> PaginatedResponse[UserResponse]:
    query = select(User)
    count_query = select(func.count(User.id))

    if role is not None:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    total = db.scalar(count_query) or 0
    offset = (page - 1) * size
    users = db.scalars(query.order_by(User.created_at.desc()).offset(offset).limit(size)).all()

    pages = (total + size - 1) // size if total > 0 else 0
    return PaginatedResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse,
    summary="Update a user's role (Admin only)",
)
def update_user_role(
    user_id: uuid.UUID,
    data: UpdateUserRoleRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserResponse:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == current_admin.id and data.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote your own admin account",
        )

    user.role = data.role
    db.commit()
    db.refresh(user)
    logger.info(
        "user role updated", extra={"target_user_id": str(user.id), "new_role": data.role.value}
    )
    return UserResponse.model_validate(user)


@router.patch(
    "/users/{user_id}/status",
    response_model=UserResponse,
    summary="Activate or deactivate a user account (Admin only)",
)
def update_user_status(
    user_id: uuid.UUID,
    data: UpdateUserStatusRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserResponse:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == current_admin.id and not data.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own admin account",
        )

    user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    logger.info(
        "user active status updated",
        extra={"target_user_id": str(user.id), "is_active": data.is_active},
    )
    return UserResponse.model_validate(user)
