"""Unit tests for incident reporting and management API (T-015)."""

from __future__ import annotations

from app.core.security import create_access_token
from app.modules.incidents.models import IncidentStatus
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


def test_submit_report_returns_202_accepted(make_client, db_session):
    client = make_client(db=db_session)
    _, citizen_token = _create_user(
        db_session, "Citizen", "citizen_rep@example.com", UserRole.CITIZEN
    )

    payload = {
        "title": "Severe flooding on Main Street",
        "raw_text": "Water levels rising fast, two families trapped on the ground floor.",
        "location_lat": 28.6139,
        "location_lon": 77.2090,
        "location_text": "Near Main Market, Sector 4",
        "idempotency_key": "custom-key-12345",
    }
    response = client.post(
        "/api/v1/incidents/reports",
        headers={"Authorization": f"Bearer {citizen_token}"},
        json=payload,
    )

    assert response.status_code == 202
    body = response.json()
    assert body["report_id"]
    assert body["incident_id"]
    assert body["idempotency_key"] == "custom-key-12345"
    assert body["processing_state"] == "queued"
    assert "queued" in body["message"].lower()


def test_submit_report_idempotency_prevents_duplicate(make_client, db_session):
    client = make_client(db=db_session)
    _, citizen_token = _create_user(
        db_session, "Citizen2", "citizen2@example.com", UserRole.CITIZEN
    )

    payload = {
        "title": "Fallen tree blocking highway",
        "raw_text": "A large tree fell across both lanes of the expressway.",
        "idempotency_key": "idemp-key-999",
    }

    # First submission
    r1 = client.post(
        "/api/v1/incidents/reports",
        headers={"Authorization": f"Bearer {citizen_token}"},
        json=payload,
    )
    assert r1.status_code == 202
    r1_body = r1.json()

    # Second submission with same key
    r2 = client.post(
        "/api/v1/incidents/reports",
        headers={"Authorization": f"Bearer {citizen_token}"},
        json=payload,
    )
    assert r2.status_code == 202
    r2_body = r2.json()

    assert r1_body["report_id"] == r2_body["report_id"]
    assert r1_body["incident_id"] == r2_body["incident_id"]


def test_track_report_status_authorization(make_client, db_session):
    client = make_client(db=db_session)
    _, citizen1_token = _create_user(db_session, "C1", "c1@example.com", UserRole.CITIZEN)
    _, citizen2_token = _create_user(db_session, "C2", "c2@example.com", UserRole.CITIZEN)
    _, auth_token = _create_user(db_session, "Auth", "auth_rep@example.com", UserRole.AUTHORITY)

    # C1 submits a report
    submission = client.post(
        "/api/v1/incidents/reports",
        headers={"Authorization": f"Bearer {citizen1_token}"},
        json={"title": "Small fire in garage", "raw_text": "Smoke coming from garage."},
    ).json()
    report_id = submission["report_id"]

    # C1 (owner) can view
    r1 = client.get(
        f"/api/v1/incidents/reports/{report_id}",
        headers={"Authorization": f"Bearer {citizen1_token}"},
    )
    assert r1.status_code == 200
    assert r1.json()["id"] == report_id

    # C2 (other citizen) cannot view
    r2 = client.get(
        f"/api/v1/incidents/reports/{report_id}",
        headers={"Authorization": f"Bearer {citizen2_token}"},
    )
    assert r2.status_code == 403

    # Authority can view
    r3 = client.get(
        f"/api/v1/incidents/reports/{report_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r3.status_code == 200


def test_list_and_get_incidents(make_client, db_session):
    client = make_client(db=db_session)
    _, citizen_token = _create_user(
        db_session, "Reporter", "reporter@example.com", UserRole.CITIZEN
    )
    _, auth_token = _create_user(
        db_session, "Authority", "authority_inc@example.com", UserRole.AUTHORITY
    )

    # Citizen cannot list incidents
    assert (
        client.get(
            "/api/v1/incidents",
            headers={"Authorization": f"Bearer {citizen_token}"},
        ).status_code
        == 403
    )

    # Submit 2 reports
    client.post(
        "/api/v1/incidents/reports",
        headers={"Authorization": f"Bearer {citizen_token}"},
        json={"title": "Emergency 1", "raw_text": "First emergency details."},
    )
    sub2 = client.post(
        "/api/v1/incidents/reports",
        headers={"Authorization": f"Bearer {citizen_token}"},
        json={"title": "Emergency 2", "raw_text": "Second emergency details."},
    ).json()

    # Authority lists incidents
    list_resp = client.get(
        "/api/v1/incidents",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] >= 2
    assert len(body["items"]) >= 2

    # Authority gets detail with linked reports
    detail_resp = client.get(
        f"/api/v1/incidents/{sub2['incident_id']}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["title"] == "Emergency 2"
    assert len(detail["reports"]) >= 1


def test_update_incident_status_and_audit(make_client, db_session):
    client = make_client(db=db_session)
    _, citizen_token = _create_user(db_session, "Citizen3", "c3@example.com", UserRole.CITIZEN)
    _, rescue_token = _create_user(db_session, "Rescue1", "res1@example.com", UserRole.RESCUE)
    _, auth_token = _create_user(db_session, "Auth1", "auth1@example.com", UserRole.AUTHORITY)

    sub = client.post(
        "/api/v1/incidents/reports",
        headers={"Authorization": f"Bearer {citizen_token}"},
        json={"title": "Gas leak reported", "raw_text": "Strong smell of gas near building."},
    ).json()
    incident_id = sub["incident_id"]

    # Rescue cannot update status (requires Authority or Admin)
    r_rescue = client.patch(
        f"/api/v1/incidents/{incident_id}/status",
        headers={"Authorization": f"Bearer {rescue_token}"},
        json={"status": "verified"},
    )
    assert r_rescue.status_code == 403

    # Authority updates status to verified
    r_auth = client.patch(
        f"/api/v1/incidents/{incident_id}/status",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"status": "verified", "notes": "Confirmed by local police unit."},
    )
    assert r_auth.status_code == 200
    assert r_auth.json()["status"] == "verified"

    # Verify audit log was recorded
    admin, admin_token = _create_user(
        db_session, "AdminAudit", "admin_aud@example.com", UserRole.ADMIN
    )
    logs_resp = client.get(
        "/api/v1/admin/audit-logs?entity=incident",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert logs_resp.status_code == 200
    audit_items = logs_resp.json()["items"]
    matching = [
        i
        for i in audit_items
        if i["action"] == "incident.status_update" and i["entity_id"] == incident_id
    ]
    assert len(matching) == 1
    assert matching[0]["payload"]["new_status"] == IncidentStatus.VERIFIED.value
