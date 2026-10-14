"""Unit tests for authentication and user management API endpoints."""

from __future__ import annotations

import time

from app.services.token_blacklist import get_token_blacklist


def test_register_citizen_success(make_client, db_session):
    client = make_client(db=db_session)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Jane Citizen",
            "email": "Jane.Citizen@Example.COM",
            "password": "Password123!",
            "phone": "+919876543210",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Jane Citizen"
    assert body["email"] == "jane.citizen@example.com"
    assert body["role"] == "citizen"
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body
    assert "id" in body


def test_register_duplicate_email_returns_409(make_client, db_session):
    client = make_client(db=db_session)
    payload = {
        "name": "First User",
        "email": "duplicate@example.com",
        "password": "Password123!",
    }
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    # Second attempt with same email in different case
    payload["email"] = "DUPLICATE@example.com"
    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


def test_register_validation_errors(make_client, db_session):
    client = make_client(db=db_session)

    # Short password
    r1 = client.post(
        "/api/v1/auth/register",
        json={"name": "Alice", "email": "alice@example.com", "password": "short"},
    )
    assert r1.status_code == 422

    # Invalid email
    r2 = client.post(
        "/api/v1/auth/register",
        json={"name": "Alice", "email": "not-an-email", "password": "Password123!"},
    )
    assert r2.status_code == 422

    # Empty name
    r3 = client.post(
        "/api/v1/auth/register",
        json={"name": "   ", "email": "alice@example.com", "password": "Password123!"},
    )
    assert r3.status_code == 422


def test_login_success(make_client, db_session):
    client = make_client(db=db_session)
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={"name": "Login User", "email": "login@example.com", "password": "SecurePassword123!"},
    )

    # Login with mixed case email
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "LOGIN@Example.com", "password": "SecurePassword123!"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


def test_login_invalid_password_returns_401(make_client, db_session):
    client = make_client(db=db_session)
    client.post(
        "/api/v1/auth/register",
        json={"name": "User", "email": "test@example.com", "password": "CorrectPassword123!"},
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "WrongPassword123!"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_nonexistent_email_returns_401(make_client, db_session):
    client = make_client(db=db_session)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "AnyPassword123!"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_get_current_user_profile(make_client, db_session):
    client = make_client(db=db_session)
    reg = client.post(
        "/api/v1/auth/register",
        json={"name": "Profile User", "email": "profile@example.com", "password": "Password123!"},
    ).json()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "profile@example.com", "password": "Password123!"},
    ).json()

    token = login_resp["access_token"]
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["id"] == reg["id"]
    assert response.json()["email"] == "profile@example.com"
    assert response.json()["role"] == "citizen"


def test_get_current_user_unauthorized(make_client, db_session):
    client = make_client(db=db_session)

    # Missing auth
    assert client.get("/api/v1/users/me").status_code == 401

    # Invalid token
    assert (
        client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid.token.value"},
        ).status_code
        == 401
    )


def test_cannot_use_refresh_token_on_protected_endpoints(make_client, db_session):
    client = make_client(db=db_session)
    client.post(
        "/api/v1/auth/register",
        json={"name": "User", "email": "refresh_guard@example.com", "password": "Password123!"},
    )
    tokens = client.post(
        "/api/v1/auth/login",
        json={"email": "refresh_guard@example.com", "password": "Password123!"},
    ).json()

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert response.status_code == 401
    assert "access token required" in response.json()["detail"]


def test_refresh_token_rotation_and_revocation(make_client, db_session):
    get_token_blacklist().reset_for_tests()
    client = make_client(db=db_session)

    client.post(
        "/api/v1/auth/register",
        json={"name": "Rotator", "email": "rotate@example.com", "password": "Password123!"},
    )
    tokens1 = client.post(
        "/api/v1/auth/login",
        json={"email": "rotate@example.com", "password": "Password123!"},
    ).json()

    # Small delay so iat/exp differ if rotated
    time.sleep(0.05)

    # First refresh succeeds
    rotate_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens1["refresh_token"]},
    )
    assert rotate_resp.status_code == 200
    tokens2 = rotate_resp.json()
    assert tokens2["access_token"]
    assert tokens2["refresh_token"]

    # Re-using the old refresh token must be rejected (revoked by rotation)
    reuse_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens1["refresh_token"]},
    )
    assert reuse_resp.status_code == 401
    assert "revoked" in reuse_resp.json()["detail"].lower()


def test_logout_revokes_refresh_token(make_client, db_session):
    get_token_blacklist().reset_for_tests()
    client = make_client(db=db_session)

    client.post(
        "/api/v1/auth/register",
        json={"name": "Logouter", "email": "logout@example.com", "password": "Password123!"},
    )
    tokens = client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "Password123!"},
    ).json()

    logout_resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout_resp.status_code == 200
    assert "logged out" in logout_resp.json()["message"].lower()

    # Using the token now fails
    refresh_after_logout = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_after_logout.status_code == 401
    assert "revoked" in refresh_after_logout.json()["detail"].lower()
