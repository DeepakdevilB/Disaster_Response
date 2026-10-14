"""API endpoints for AI predictions, human overrides, and cluster summarization (T-034, T-035)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.summarizer import SituationSummary, summarize_cluster
from app.api.deps import get_db
from app.core.rbac import require_roles
from app.modules.ai.models import AIPrediction
from app.modules.ai.schemas import (
    AIPredictionResponse,
    PredictionOverrideRequest,
    SituationSummaryResponse,
)
from app.modules.audit.service import record_audit_log
from app.modules.incidents.models import (
    Incident,
    IncidentCategory,
    IncidentReport,
    IncidentSeverity,
)
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/predictions", tags=["ai-predictions"])


@router.get(
    "/reports/{report_id}",
    response_model=AIPredictionResponse,
    summary="Get AI triage prediction for an incident report",
)
def get_prediction_for_report(
    report_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_roles(UserRole.AUTHORITY, UserRole.ADMIN, UserRole.RESCUE))
    ],
) -> AIPredictionResponse:
    pred = db.scalar(select(AIPrediction).where(AIPrediction.report_id == report_id))
    if not pred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AI prediction not found for this report"
        )
    return AIPredictionResponse.model_validate(pred)


@router.post(
    "/{prediction_id}/override",
    response_model=AIPredictionResponse,
    summary="Authority human-in-the-loop override of AI classification or severity",
)
def override_prediction(
    prediction_id: uuid.UUID,
    payload: PredictionOverrideRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.AUTHORITY, UserRole.ADMIN))],
) -> AIPredictionResponse:
    pred = db.scalar(select(AIPrediction).where(AIPrediction.id == prediction_id))
    if not pred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI prediction not found")

    if payload.override_category is None and payload.override_severity is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Must specify at least one of override_category or override_severity",
        )

    now = datetime.now(UTC)
    changes = {}

    if payload.override_category is not None:
        try:
            valid_cat = IncidentCategory(payload.override_category.lower())
            pred.override_category = valid_cat.value
            changes["category"] = valid_cat.value
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid category: {payload.override_category}",
            ) from exc

    if payload.override_severity is not None:
        try:
            valid_sev = IncidentSeverity(payload.override_severity.upper())
            pred.override_severity = valid_sev.value
            changes["severity"] = valid_sev.value
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid severity: {payload.override_severity}",
            ) from exc

    pred.override_by_id = current_user.id
    pred.override_reason = payload.reason
    pred.override_at = now

    # Also sync updated values onto parent report and canonical incident if present
    report = db.scalar(select(IncidentReport).where(IncidentReport.id == pred.report_id))
    if report:
        if pred.override_category:
            report.predicted_category = IncidentCategory(pred.override_category)
        if pred.override_severity:
            report.predicted_severity = IncidentSeverity(pred.override_severity)

        if report.incident_id:
            incident = db.scalar(select(Incident).where(Incident.id == report.incident_id))
            if incident:
                if pred.override_category:
                    incident.category = IncidentCategory(pred.override_category)
                if pred.override_severity:
                    incident.severity = IncidentSeverity(pred.override_severity)

    db.commit()
    db.refresh(pred)

    record_audit_log(
        db=db,
        actor_id=current_user.id,
        action="prediction.override",
        entity="ai_prediction",
        entity_id=pred.id,
        payload={
            "report_id": str(pred.report_id),
            "reason": payload.reason,
            "changes": changes,
        },
    )

    return AIPredictionResponse.model_validate(pred)


@router.post(
    "/incidents/{incident_id}/summarize",
    response_model=SituationSummaryResponse,
    summary="Generate on-demand situation summary for an incident cluster",
)
def summarize_incident_cluster(
    incident_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_roles(UserRole.AUTHORITY, UserRole.ADMIN, UserRole.RESCUE))
    ],
) -> SituationSummaryResponse:
    incident = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    reports = db.scalars(
        select(IncidentReport).where(IncidentReport.incident_id == incident_id)
    ).all()

    report_dicts = [
        {
            "category": r.predicted_category.value
            if r.predicted_category
            else incident.category.value,
            "severity": r.predicted_severity.value
            if r.predicted_severity
            else incident.severity.value,
            "raw_text": r.raw_text,
            "location_text": r.location_text or incident.location_text,
            "people_count": 0,
        }
        for r in reports
    ]

    # If no attached reports, summarize incident itself
    if not report_dicts:
        report_dicts = [
            {
                "category": incident.category.value,
                "severity": incident.severity.value,
                "raw_text": incident.description or incident.title,
                "location_text": incident.location_text,
                "people_count": incident.people_affected or 0,
            }
        ]

    summary: SituationSummary = summarize_cluster(report_dicts)
    return SituationSummaryResponse(**summary.model_dump())
