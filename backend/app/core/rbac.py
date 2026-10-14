"""Role-based access control (RBAC) dependencies."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.modules.users.models import User, UserRole


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    """Return a dependency that enforces the current user has one of the allowed roles.

    Deny-by-default: If the user's role is not in allowed_roles, HTTP 403 is raised.
    """

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: requires one of {[r.value for r in allowed_roles]}",
            )
        return current_user

    return role_checker


# Role shortcut dependencies
require_admin = require_roles(UserRole.ADMIN)
require_authority = require_roles(UserRole.AUTHORITY, UserRole.ADMIN)
require_responder = require_roles(UserRole.AUTHORITY, UserRole.RESCUE, UserRole.ADMIN)
require_citizen = require_roles(
    UserRole.CITIZEN, UserRole.AUTHORITY, UserRole.RESCUE, UserRole.ADMIN
)
