"""Unit tests for resource and rescue-team management API (T-021)."""

from __future__ import annotations

import uuid

from app.core.security import create_access_token
from app.modules.resources.models import Resource, ResourceStatus, ResourceType
from app.modules.users.models import User, UserRole


def _create_user(db, name: str, email: str, role: UserRole) -> tuple[User, str]:
    user = User(
        name=name,
        email=email.lower(),
        password_hash="fake-hash",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=str(user.id), role=role.value, email=user.email)
    return user, token


def test_create_resource_by_authority(make_client, db_session):
    client = make_client(db=db_session)
    _, auth_token = _create_user(
        db_session, "Authority", "auth_res@example.com", UserRole.AUTHORITY
    )

    payload = {
        "name": "Rescue-Boat-01",
        "type": "boat",
        "capacity": 8,
        "latitude": 12.9716,
        "longitude": 77.5946,
    }
    response = client.post(
        "/api/v1/resources",
        headers={"Authorization": f"Bearer {auth_token}"},
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Rescue-Boat-01"
    assert data["type"] == "boat"
    assert data["status"] == "available"
    assert data["capacity"] == 8
    assert data["latitude"] == 12.9716
    assert data["longitude"] == 77.5946


def test_create_resource_forbidden_for_citizen(make_client, db_session):
    client = make_client(db=db_session)
    _, citizen_token = _create_user(
        db_session, "Citizen", "citizen_res@example.com", UserRole.CITIZEN
    )

    payload = {
        "name": "Rescue-Boat-02",
        "type": "boat",
        "capacity": 5,
    }
    response = client.post(
        "/api/v1/resources",
        headers={"Authorization": f"Bearer {citizen_token}"},
        json=payload,
    )
    assert response.status_code == 403


def test_create_duplicate_resource_name_conflict(make_client, db_session):
    client = make_client(db=db_session)
    _, auth_token = _create_user(db_session, "Admin", "admin_res@example.com", UserRole.ADMIN)

    payload = {
        "name": "Ambulance-Central-01",
        "type": "ambulance",
        "capacity": 2,
    }
    res1 = client.post(
        "/api/v1/resources", headers={"Authorization": f"Bearer {auth_token}"}, json=payload
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/api/v1/resources", headers={"Authorization": f"Bearer {auth_token}"}, json=payload
    )
    assert res2.status_code == 409


def test_list_and_filter_resources(make_client, db_session):
    client = make_client(db=db_session)
    _, auth_token = _create_user(
        db_session, "Authority", "auth_list@example.com", UserRole.AUTHORITY
    )

    r1 = Resource(
        name="Amb-1", type=ResourceType.AMBULANCE, status=ResourceStatus.AVAILABLE, capacity=2
    )
    r2 = Resource(
        name="Boat-1", type=ResourceType.BOAT, status=ResourceStatus.AVAILABLE, capacity=10
    )
    r3 = Resource(
        name="Amb-2", type=ResourceType.AMBULANCE, status=ResourceStatus.ASSIGNED, capacity=2
    )
    db_session.add_all([r1, r2, r3])
    db_session.commit()

    # Filter by type
    res = client.get(
        "/api/v1/resources?type=ambulance", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert all(r["type"] == "ambulance" for r in data)

    # Filter by status
    res = client.get(
        "/api/v1/resources?status=assigned", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "Amb-2"


def test_update_resource_status_and_location(make_client, db_session):
    client = make_client(db=db_session)
    _, rescue_token = _create_user(
        db_session, "Rescue", "rescue_patch@example.com", UserRole.RESCUE
    )

    r = Resource(
        name="Team-Alpha",
        type=ResourceType.RESCUE_TEAM,
        status=ResourceStatus.AVAILABLE,
        capacity=6,
    )
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)

    patch_payload = {
        "status": "assigned",
        "latitude": 13.0827,
        "longitude": 80.2707,
    }
    response = client.patch(
        f"/api/v1/resources/{r.id}",
        headers={"Authorization": f"Bearer {rescue_token}"},
        json=patch_payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "assigned"
    assert data["latitude"] == 13.0827
    assert data["longitude"] == 80.2707


def test_get_resource_not_found(make_client, db_session):
    client = make_client(db=db_session)
    _, auth_token = _create_user(db_session, "Authority", "auth_nf@example.com", UserRole.AUTHORITY)

    response = client.get(
        f"/api/v1/resources/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404
