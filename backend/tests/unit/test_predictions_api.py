"""Unit tests for AI predictions API and human override workflow (T-035)."""

from __future__ import annotations

import uuid

from app.core.security import create_access_token
from app.modules.ai.models import AIPrediction
from app.modules.incidents.models import (
    Incident,
    IncidentCategory,
    IncidentReport,
    IncidentSeverity,
    ReportProcessingState,
)
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


def test_get_prediction_for_report(make_client, db_session):
    client = make_client(db=db_session)
    user, auth_token = _create_user(
        db_session, "Authority", "auth_pred@example.com", UserRole.AUTHORITY
    )

    report = IncidentReport(
        user_id=user.id,
        raw_text="Chemical spill with toxic fumes in Sector 10.",
        idempotency_key="pred-test-key-01",
        processing_state=ReportProcessingState.DONE,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    prediction = AIPrediction(
        report_id=report.id,
        model_name="test_model",
        model_version="v1.0.0",
        predicted_category="fire",
        category_confidence=0.88,
        predicted_severity="HIGH",
        severity_confidence=0.91,
        extracted_entities={"people_count": 0, "location": "Sector 10"},
        raw_output={},
    )
    db_session.add(prediction)
    db_session.commit()
    db_session.refresh(prediction)

    response = client.get(
        f"/api/v1/predictions/reports/{report.id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["predicted_category"] == "fire"
    assert data["predicted_severity"] == "HIGH"
    assert data["category_confidence"] == 0.88


def test_authority_override_prediction(make_client, db_session):
    client = make_client(db=db_session)
    auth_user, auth_token = _create_user(
        db_session, "Authority Officer", "auth_override@example.com", UserRole.AUTHORITY
    )

    incident = Incident(
        title="Fire incident",
        description="Warehouse fire with trapped people",
        category=IncidentCategory.FIRE,
        severity=IncidentSeverity.MEDIUM,
    )
    db_session.add(incident)
    db_session.commit()

    report = IncidentReport(
        user_id=auth_user.id,
        incident_id=incident.id,
        raw_text="Warehouse fire with 4 people trapped",
        idempotency_key="override-key-01",
    )
    db_session.add(report)
    db_session.commit()

    pred = AIPrediction(
        report_id=report.id,
        model_name="test_model",
        model_version="v1.0.0",
        predicted_category="fire",
        category_confidence=0.75,
        predicted_severity="MEDIUM",
        severity_confidence=0.70,
        extracted_entities={"people_count": 4},
        raw_output={},
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)

    override_payload = {
        "override_severity": "CRITICAL",
        "reason": "Field inspection confirmed 4 victims trapped with acute risk of structural collapse",
    }
    response = client.post(
        f"/api/v1/predictions/{pred.id}/override",
        headers={"Authorization": f"Bearer {auth_token}"},
        json=override_payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["override_severity"] == "CRITICAL"
    assert data["final_severity"] == "CRITICAL"
    assert data["override_reason"] == override_payload["reason"]

    # Verify parent report & incident synchronized
    db_session.refresh(report)
    assert report.predicted_severity == IncidentSeverity.CRITICAL
    db_session.refresh(incident)
    assert incident.severity == IncidentSeverity.CRITICAL


def test_citizen_cannot_override_prediction(make_client, db_session):
    client = make_client(db=db_session)
    _, citizen_token = _create_user(
        db_session, "Citizen", "citizen_override@example.com", UserRole.CITIZEN
    )

    response = client.post(
        f"/api/v1/predictions/{uuid.uuid4()}/override",
        headers={"Authorization": f"Bearer {citizen_token}"},
        json={"override_severity": "CRITICAL", "reason": "Unauthorized override attempt"},
    )
    assert response.status_code == 403


def test_summarize_incident_endpoint(make_client, db_session):
    client = make_client(db=db_session)
    _, auth_token = _create_user(
        db_session, "Authority Summary", "auth_sum@example.com", UserRole.AUTHORITY
    )

    incident = Incident(
        title="Monsoon flooding",
        description="Severe monsoon flooding in sector 14",
        category=IncidentCategory.FLOOD,
        severity=IncidentSeverity.CRITICAL,
        location_text="Sector 14 near metro",
        people_affected=10,
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    response = client.post(
        f"/api/v1/predictions/incidents/{incident.id}/summarize",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert data["primary_category"] == "flood"
    assert len(data["key_risks"]) >= 1
    assert len(data["recommended_actions"]) >= 1
