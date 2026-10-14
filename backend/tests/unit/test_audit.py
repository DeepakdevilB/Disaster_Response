"""Unit tests for audit logging service and endpoints."""

from __future__ import annotations

import uuid

from app.core.security import create_access_token
from app.modules.audit.service import list_audit_logs, record_audit_log
from app.modules.users.models import User, UserRole


def test_record_and_list_audit_log(db_session):
    actor_id = uuid.uuid4()
    entry = record_audit_log(
        db_session,
        actor_id=actor_id,
        action="incident.verify",
        entity="incident",
        entity_id="inc-123",
        payload={"previous_status": "new", "new_status": "verified"},
    )

    assert entry.id is not None
    assert entry.actor_id == actor_id
    assert entry.action == "incident.verify"
    assert entry.payload["new_status"] == "verified"

    # List with filtering
    items, total = list_audit_logs(db_session, action="incident.verify")
    assert total == 1
    assert items[0].entity_id == "inc-123"

    # Filter with non-matching action returns 0
    items, total = list_audit_logs(db_session, action="nonexistent")
    assert total == 0


def test_admin_role_change_records_audit_log(make_client, db_session):
    client = make_client(db=db_session)
    admin = User(
        name="Admin",
        email="admin_audit@example.com",
        password_hash="hash",
        role=UserRole.ADMIN,
        is_active=True,
    )
    target = User(
        name="Target",
        email="target_audit@example.com",
        password_hash="hash",
        role=UserRole.CITIZEN,
        is_active=True,
    )
    db_session.add_all([admin, target])
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(target)

    admin_token = create_access_token(
        subject=str(admin.id), role=admin.role.value, email=admin.email
    )

    # Change role
    client.patch(
        f"/api/v1/admin/users/{target.id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "rescue"},
    )

    # Fetch audit logs via API
    logs_resp = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert logs_resp.status_code == 200
    body = logs_resp.json()
    assert body["total"] >= 1
    action_logs = [item for item in body["items"] if item["action"] == "user.role_update"]
    assert len(action_logs) == 1
    assert action_logs[0]["payload"]["old_role"] == "citizen"
    assert action_logs[0]["payload"]["new_role"] == "rescue"
