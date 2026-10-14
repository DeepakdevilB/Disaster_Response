"""Incident reporting and incident management API routes."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rbac import require_authority, require_citizen, require_responder
from app.db.session import get_db
from app.modules.incidents.models import (
    ACTIVE_INCIDENT_STATUSES,
    Incident,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
)
from app.modules.incidents.priority import priority_engine
from app.modules.incidents.schemas import (
    CreateReportRequest,
    IncidentDetailResponse,
    IncidentReportResponse,
    IncidentSummaryResponse,
    ReportSubmissionResponse,
    UpdateIncidentStatusRequest,
)
from app.modules.incidents.service import (
    extract_coordinates,
    get_incident_by_id,
    get_report_by_id,
    list_incidents,
    submit_report,
    update_incident_status,
)
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _to_summary_response(incident) -> IncidentSummaryResponse:
    lat, lon = extract_coordinates(incident.location)
    return IncidentSummaryResponse(
        id=incident.id,
        title=incident.title,
        description=incident.description,
        category=incident.category,
        severity=incident.severity,
        status=incident.status,
        priority_score=incident.priority_score,
        people_affected=incident.people_affected,
        location_text=incident.location_text,
        location_lat=lat,
        location_lon=lon,
        report_count=incident.report_count,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )


def _to_report_response(report) -> IncidentReportResponse:
    lat, lon = extract_coordinates(report.location)
    return IncidentReportResponse(
        id=report.id,
        incident_id=report.incident_id,
        user_id=report.user_id,
        raw_text=report.raw_text,
        location_text=report.location_text,
        location_lat=lat,
        location_lon=lon,
        idempotency_key=report.idempotency_key,
        processing_state=report.processing_state,
        processing_attempts=report.processing_attempts,
        created_at=report.created_at,
    )


@router.post(
    "/reports",
    response_model=ReportSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit an emergency incident report (HTTP 202 Accepted)",
)
def create_report(
    data: CreateReportRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(require_citizen),
    db: Session = Depends(get_db),
) -> ReportSubmissionResponse:
    report, is_new = submit_report(
        db=db,
        user=current_user,
        data=data,
        header_idempotency_key=idempotency_key,
    )
    message = (
        "Report submitted and queued for AI classification"
        if is_new
        else "Duplicate submission recognized; returning existing report tracking information"
    )
    return ReportSubmissionResponse(
        report_id=report.id,
        incident_id=report.incident_id,
        idempotency_key=report.idempotency_key,
        processing_state=report.processing_state,
        message=message,
    )


@router.get(
    "/reports/{report_id}",
    response_model=IncidentReportResponse,
    summary="Track an incident report processing status",
)
def get_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncidentReportResponse:
    report = get_report_by_id(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    # Authorize: owner of report, or Authority/Rescue/Admin
    is_privileged = current_user.role in (UserRole.AUTHORITY, UserRole.RESCUE, UserRole.ADMIN)
    if not is_privileged and report.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: you do not have permission to view this report",
        )

    return _to_report_response(report)


@router.get(
    "",
    summary="List incidents with pagination and filters (Authority/Rescue only)",
)
def get_incidents(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: IncidentStatus | None = Query(default=None),
    category: IncidentCategory | None = Query(default=None),
    severity: IncidentSeverity | None = Query(default=None),
    min_priority: Decimal | None = Query(default=None),
    max_priority: Decimal | None = Query(default=None),
    current_user: User = Depends(require_responder),
    db: Session = Depends(get_db),
) -> dict:
    incidents, total = list_incidents(
        db,
        page=page,
        size=size,
        status=status,
        category=category,
        severity=severity,
        min_priority=min_priority,
        max_priority=max_priority,
    )
    pages = (total + size - 1) // size if total > 0 else 0
    return {
        "items": [_to_summary_response(inc) for inc in incidents],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.get(
    "/ranked",
    response_model=list[IncidentSummaryResponse],
    summary="Priority-ranked feed of active incidents (T-042)",
)
def get_ranked_incidents(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_responder),
    db: Session = Depends(get_db),
) -> list[IncidentSummaryResponse]:
    active_incidents = (
        db.query(Incident).filter(Incident.status.in_(ACTIVE_INCIDENT_STATUSES)).all()
    )
    # Recalculate dynamic priority scores including waiting time
    for inc in active_incidents:
        calc = priority_engine.compute_priority(
            severity=inc.severity.value if inc.severity else None,
            people_affected=inc.people_affected,
            created_at=inc.created_at,
            incident_text=f"{inc.title} {inc.description}",
        )
        inc.priority_score = Decimal(str(calc.priority_score))

    active_incidents.sort(key=lambda x: x.priority_score or Decimal(0), reverse=True)
    return [_to_summary_response(inc) for inc in active_incidents[:limit]]


@router.get(
    "/{incident_id}/priority-breakdown",
    summary="Get explainable factor breakdown for an incident's priority score (T-041)",
)
def get_priority_breakdown(
    incident_id: uuid.UUID,
    current_user: User = Depends(require_responder),
    db: Session = Depends(get_db),
):
    incident = get_incident_by_id(db, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    calc = priority_engine.compute_priority(
        severity=incident.severity.value if incident.severity else None,
        people_affected=incident.people_affected,
        created_at=incident.created_at,
        incident_text=f"{incident.title} {incident.description}",
    )
    return {
        "incident_id": str(incident.id),
        "priority_score": calc.priority_score,
        "breakdown": calc.breakdown,
    }


@router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    summary="Get detailed incident information (Authority/Rescue only)",
)
def get_incident(
    incident_id: uuid.UUID,
    current_user: User = Depends(require_responder),
    db: Session = Depends(get_db),
) -> IncidentDetailResponse:
    incident = get_incident_by_id(db, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    lat, lon = extract_coordinates(incident.location)
    return IncidentDetailResponse(
        id=incident.id,
        title=incident.title,
        description=incident.description,
        category=incident.category,
        severity=incident.severity,
        status=incident.status,
        priority_score=incident.priority_score,
        people_affected=incident.people_affected,
        location_text=incident.location_text,
        location_lat=lat,
        location_lon=lon,
        report_count=incident.report_count,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        reports=[_to_report_response(r) for r in incident.reports],
    )


@router.patch(
    "/{incident_id}/status",
    response_model=IncidentDetailResponse,
    summary="Update incident status (Authority/Admin only)",
)
def update_status(
    incident_id: uuid.UUID,
    data: UpdateIncidentStatusRequest,
    current_authority: User = Depends(require_authority),
    db: Session = Depends(get_db),
) -> IncidentDetailResponse:
    try:
        incident = update_incident_status(
            db,
            incident_id=incident_id,
            new_status=data.status,
            actor=current_authority,
            notes=data.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    lat, lon = extract_coordinates(incident.location)
    return IncidentDetailResponse(
        id=incident.id,
        title=incident.title,
        description=incident.description,
        category=incident.category,
        severity=incident.severity,
        status=incident.status,
        priority_score=incident.priority_score,
        people_affected=incident.people_affected,
        location_text=incident.location_text,
        location_lat=lat,
        location_lon=lon,
        report_count=incident.report_count,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        reports=[_to_report_response(r) for r in incident.reports],
    )
