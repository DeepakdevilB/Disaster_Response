"""Business logic for incidents and citizen incident reports."""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.modules.audit.service import record_audit_log
from app.modules.incidents.models import (
    Incident,
    IncidentCategory,
    IncidentReport,
    IncidentSeverity,
    IncidentStatus,
    ReportProcessingState,
)
from app.modules.incidents.schemas import CreateReportRequest
from app.modules.users.models import User
from app.services.queue import publish_report_submitted_event

logger = logging.getLogger(__name__)


def extract_coordinates(location: Any) -> tuple[float | None, float | None]:
    """Extract (latitude, longitude) from a geometry element or string."""
    if location is None:
        return None, None
    if isinstance(location, str) and location.startswith("POINT"):
        try:
            parts = location.replace("POINT", "").replace("(", "").replace(")", "").strip().split()
            lon, lat = float(parts[0]), float(parts[1])
            return lat, lon
        except (ValueError, IndexError):
            return None, None
    try:
        from geoalchemy2.shape import to_shape

        shape = to_shape(location)
        return float(shape.y), float(shape.x)
    except Exception:
        return None, None


def submit_report(
    db: Session,
    user: User,
    data: CreateReportRequest,
    header_idempotency_key: str | None = None,
) -> tuple[IncidentReport, bool]:
    """Submit a citizen incident report.

    Idempotent: If a report with the same idempotency key exists,
    returns it without creating a duplicate.

    Returns:
        tuple[IncidentReport, bool]: (report, is_newly_created)
    """
    key = data.idempotency_key or header_idempotency_key or str(uuid.uuid4())

    existing = db.scalar(select(IncidentReport).where(IncidentReport.idempotency_key == key))
    if existing is not None:
        logger.info(
            "idempotent duplicate report submission ignored",
            extra={"idempotency_key": key, "report_id": str(existing.id)},
        )
        return existing, False

    # Geometry: WKT representation for location
    geom = None
    if data.location_lat is not None and data.location_lon is not None:
        wkt = f"POINT({data.location_lon} {data.location_lat})"
        if db.bind is not None and db.bind.dialect.name == "sqlite":
            geom = wkt
        else:
            geom = WKTElement(wkt, srid=4326)

    # Initial canonical incident
    incident = Incident(
        title=data.title.strip(),
        description=data.raw_text.strip(),
        location=geom,
        location_text=data.location_text.strip() if data.location_text else None,
        status=IncidentStatus.NEW,
        report_count=1,
    )
    db.add(incident)
    db.flush()

    report = IncidentReport(
        incident_id=incident.id,
        user_id=user.id,
        raw_text=data.raw_text.strip(),
        location=geom,
        location_text=data.location_text.strip() if data.location_text else None,
        idempotency_key=key,
        processing_state=ReportProcessingState.QUEUED,
        processing_attempts=0,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    db.refresh(incident)

    # Publish to queue for NLP and dedup workers
    publish_report_submitted_event(
        report_id=report.id,
        incident_id=incident.id,
        user_id=user.id,
        raw_text=report.raw_text,
        location_lat=data.location_lat,
        location_lon=data.location_lon,
        location_text=data.location_text,
    )

    logger.info(
        "incident report accepted and queued",
        extra={"report_id": str(report.id), "incident_id": str(incident.id)},
    )
    return report, True


def get_report_by_id(db: Session, report_id: uuid.UUID) -> IncidentReport | None:
    return db.scalar(select(IncidentReport).where(IncidentReport.id == report_id))


def list_incidents(
    db: Session,
    *,
    page: int = 1,
    size: int = 20,
    status: IncidentStatus | None = None,
    category: IncidentCategory | None = None,
    severity: IncidentSeverity | None = None,
    min_priority: Decimal | None = None,
    max_priority: Decimal | None = None,
) -> tuple[list[Incident], int]:
    query = select(Incident)
    count_query = select(func.count(Incident.id))

    if status is not None:
        query = query.where(Incident.status == status)
        count_query = count_query.where(Incident.status == status)
    if category is not None:
        query = query.where(Incident.category == category)
        count_query = count_query.where(Incident.category == category)
    if severity is not None:
        query = query.where(Incident.severity == severity)
        count_query = count_query.where(Incident.severity == severity)
    if min_priority is not None:
        query = query.where(Incident.priority_score >= min_priority)
        count_query = count_query.where(Incident.priority_score >= min_priority)
    if max_priority is not None:
        query = query.where(Incident.priority_score <= max_priority)
        count_query = count_query.where(Incident.priority_score <= max_priority)

    total = db.scalar(count_query) or 0
    offset = (page - 1) * size
    items = db.scalars(query.order_by(Incident.created_at.desc()).offset(offset).limit(size)).all()
    return list(items), total


def get_incident_by_id(db: Session, incident_id: uuid.UUID) -> Incident | None:
    return db.scalar(
        select(Incident).options(joinedload(Incident.reports)).where(Incident.id == incident_id)
    )


def update_incident_status(
    db: Session,
    incident_id: uuid.UUID,
    new_status: IncidentStatus,
    actor: User,
    notes: str | None = None,
) -> Incident:
    incident = get_incident_by_id(db, incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")

    old_status = incident.status.value
    incident.status = new_status
    db.commit()
    db.refresh(incident)

    record_audit_log(
        db,
        actor_id=actor.id,
        action="incident.status_update",
        entity="incident",
        entity_id=str(incident.id),
        payload={"old_status": old_status, "new_status": new_status.value, "notes": notes},
    )

    logger.info(
        "incident status updated",
        extra={
            "incident_id": str(incident.id),
            "old_status": old_status,
            "new_status": new_status.value,
        },
    )
    return incident
