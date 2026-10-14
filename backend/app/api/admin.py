"""Admin user management endpoints."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rbac import require_admin
from app.db.session import get_db
from app.modules.audit.service import list_audit_logs, record_audit_log
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


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: uuid.UUID | None
    action: str
    entity: str
    entity_id: str | None
    payload: dict[str, Any]
    created_at: datetime


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

    old_role = user.role.value
    user.role = data.role
    db.commit()
    db.refresh(user)

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="user.role_update",
        entity="user",
        entity_id=str(user.id),
        payload={"old_role": old_role, "new_role": data.role.value},
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

    old_status = user.is_active
    user.is_active = data.is_active
    db.commit()
    db.refresh(user)

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="user.status_update",
        entity="user",
        entity_id=str(user.id),
        payload={"old_active": old_status, "new_active": data.is_active},
    )

    return UserResponse.model_validate(user)


@router.get(
    "/audit-logs",
    response_model=PaginatedResponse[AuditLogResponse],
    summary="View system audit logs (Admin only)",
)
def get_audit_logs(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None),
    entity: str | None = Query(default=None),
    actor_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> PaginatedResponse[AuditLogResponse]:
    items, total = list_audit_logs(
        db,
        page=page,
        size=size,
        action=action,
        entity=entity,
        actor_id=actor_id,
    )
    pages = (total + size - 1) // size if total > 0 else 0
    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
