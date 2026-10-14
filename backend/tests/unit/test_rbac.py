"""Unit tests for role-based access control (RBAC) and admin endpoints."""

from __future__ import annotations

from app.core.security import create_access_token, hash_password
from app.modules.users.models import User, UserRole


def _create_user(
    db,
    name: str,
    email: str,
    role: UserRole = UserRole.CITIZEN,
    is_active: bool = True,
) -> tuple[User, str]:
    user = User(
        name=name,
        email=email.lower(),
        password_hash=hash_password("Password123!"),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=str(user.id), role=role.value, email=user.email)
    return user, token


def test_unauthenticated_request_to_admin_route_is_rejected(make_client, db_session):
    client = make_client(db=db_session)
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 401


def test_citizen_cannot_access_admin_route(make_client, db_session):
    client = make_client(db=db_session)
    _, citizen_token = _create_user(db_session, "Citizen", "citizen@example.com", UserRole.CITIZEN)

    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


def test_rescue_cannot_access_admin_route(make_client, db_session):
    client = make_client(db=db_session)
    _, rescue_token = _create_user(db_session, "Rescue", "rescue@example.com", UserRole.RESCUE)

    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {rescue_token}"},
    )
    assert response.status_code == 403


def test_authority_cannot_access_admin_route(make_client, db_session):
    client = make_client(db=db_session)
    _, auth_token = _create_user(db_session, "Auth", "auth@example.com", UserRole.AUTHORITY)

    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 403


def test_admin_can_list_users(make_client, db_session):
    client = make_client(db=db_session)
    _create_user(db_session, "Admin", "admin@example.com", UserRole.ADMIN)
    _, admin_token = _create_user(db_session, "Admin2", "admin2@example.com", UserRole.ADMIN)
    _create_user(db_session, "User1", "user1@example.com", UserRole.CITIZEN)

    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 3
    assert len(body["items"]) >= 3


def test_admin_can_update_user_role(make_client, db_session):
    client = make_client(db=db_session)
    _, admin_token = _create_user(db_session, "Admin", "admin@example.com", UserRole.ADMIN)
    citizen, _ = _create_user(db_session, "Target", "target@example.com", UserRole.CITIZEN)

    response = client.patch(
        f"/api/v1/admin/users/{citizen.id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "authority"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "authority"

    # Reload from DB
    db_session.refresh(citizen)
    assert citizen.role == UserRole.AUTHORITY


def test_admin_cannot_demote_themselves(make_client, db_session):
    client = make_client(db=db_session)
    admin, admin_token = _create_user(db_session, "Admin", "admin@example.com", UserRole.ADMIN)

    response = client.patch(
        f"/api/v1/admin/users/{admin.id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "citizen"},
    )
    assert response.status_code == 400
    assert "Cannot demote your own admin account" in response.json()["detail"]


def test_admin_can_deactivate_and_activate_user(make_client, db_session):
    client = make_client(db=db_session)
    _, admin_token = _create_user(db_session, "Admin", "admin@example.com", UserRole.ADMIN)
    target, target_token = _create_user(
        db_session, "Deactivatee", "deact@example.com", UserRole.CITIZEN
    )

    # Deactivate
    r1 = client.patch(
        f"/api/v1/admin/users/{target.id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert r1.status_code == 200
    assert r1.json()["is_active"] is False

    # Deactivated user cannot use token for protected routes
    check_resp = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {target_token}"},
    )
    assert check_resp.status_code == 403

    # Reactivate
    r2 = client.patch(
        f"/api/v1/admin/users/{target.id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": True},
    )
    assert r2.status_code == 200
    assert r2.json()["is_active"] is True


def test_admin_cannot_deactivate_themselves(make_client, db_session):
    client = make_client(db=db_session)
    admin, admin_token = _create_user(db_session, "Admin", "admin@example.com", UserRole.ADMIN)

    response = client.patch(
        f"/api/v1/admin/users/{admin.id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert response.status_code == 400
    assert "Cannot deactivate your own admin account" in response.json()["detail"]
