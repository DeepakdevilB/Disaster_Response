"""Unit tests for async AI worker queue consumer (T-033)."""

from __future__ import annotations

import uuid

import pytest

from app.modules.incidents.models import (
    Incident,
    IncidentCategory,
    IncidentReport,
    IncidentSeverity,
    ReportProcessingState,
)
from app.modules.users.models import User, UserRole
from app.workers.ai_worker import WorkerProcessingError, process_report_ai_job


def _create_user(db, name: str, email: str, role: UserRole) -> User:
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
    return user


def test_ai_worker_processes_report_successfully(db_session):
    user = _create_user(db_session, "Citizen Worker", "worker_cit@example.com", UserRole.CITIZEN)

    incident = Incident(
        title="Flooding emergency",
        description="Severe flooding in sector 14",
        category=IncidentCategory.OTHER,
        severity=IncidentSeverity.MEDIUM,
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    report = IncidentReport(
        user_id=user.id,
        incident_id=incident.id,
        raw_text="Extreme flood water in Sector 14, 5 people trapped on roof! Urgent boat needed!",
        idempotency_key="worker-test-key-01",
        processing_state=ReportProcessingState.QUEUED,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    # Execute worker processing
    prediction = process_report_ai_job(db_session, report.id)

    assert prediction is not None
    assert prediction.report_id == report.id
    assert prediction.predicted_category == "flood"
    assert prediction.predicted_severity in ("HIGH", "CRITICAL")
    assert prediction.extracted_entities["people_count"] == 5

    # Verify report state updated
    db_session.refresh(report)
    assert report.processing_state == ReportProcessingState.DONE
    assert report.predicted_category == IncidentCategory.FLOOD

    # Verify incident updated
    db_session.refresh(incident)
    assert incident.category == IncidentCategory.FLOOD


def test_ai_worker_idempotency(db_session):
    user = _create_user(db_session, "Citizen Worker 2", "worker_cit2@example.com", UserRole.CITIZEN)

    report = IncidentReport(
        user_id=user.id,
        raw_text="Fire broke out in warehouse near market, 2 injured.",
        idempotency_key="worker-test-key-02",
        processing_state=ReportProcessingState.QUEUED,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    pred1 = process_report_ai_job(db_session, report.id)
    pred2 = process_report_ai_job(db_session, report.id)

    # Must return exact same prediction without re-running or duplicating
    assert pred1.id == pred2.id


def test_ai_worker_nonexistent_report_raises_error(db_session):
    with pytest.raises(WorkerProcessingError, match="not found in database"):
        process_report_ai_job(db_session, uuid.uuid4())
