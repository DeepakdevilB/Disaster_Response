"""Canonical incidents and the raw citizen/team reports that feed them."""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from geoalchemy2 import WKBElement
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.types import UUIDPrimaryKeyMixin, geography_point, pg_enum

if TYPE_CHECKING:
    from app.modules.assignments.models import Assignment


class IncidentCategory(enum.StrEnum):
    MEDICAL = "medical"
    RESCUE = "rescue"
    INFRASTRUCTURE = "infrastructure"
    FIRE = "fire"
    FLOOD = "flood"
    OTHER = "other"


class IncidentSeverity(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(enum.StrEnum):
    NEW = "new"
    VERIFIED = "verified"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class ReportProcessingState(enum.StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


#: Incidents still needing attention - the hot set for dashboards and the ranked feed.
ACTIVE_INCIDENT_STATUSES = (
    IncidentStatus.NEW,
    IncidentStatus.VERIFIED,
    IncidentStatus.ASSIGNED,
    IncidentStatus.IN_PROGRESS,
)
_ACTIVE_INCIDENT_SQL = "status IN ('new', 'verified', 'assigned', 'in_progress')"


class Incident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A real-world emergency. Several duplicate reports may be merged into one incident.

    ``category``/``severity``/``priority_score`` are NULL until the AI workers fill them in
    (AI never runs inside the request). ``zone_id`` is intentionally deferred until the
    ``disaster_zones`` table exists (see docs/adr/0003-defer-zone-id.md).
    """

    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("people_affected >= 0", name="people_affected_non_negative"),
        CheckConstraint(
            "priority_score IS NULL OR (priority_score >= 0 AND priority_score <= 100)",
            name="priority_score_range",
        ),
        CheckConstraint("report_count >= 1", name="report_count_positive"),
        Index("ix_incidents_location", "location", postgresql_using="gist"),
        Index("ix_incidents_created_at", "created_at"),
        # Dashboard: filter by status, order by priority.
        Index("ix_incidents_status_priority_score", "status", text("priority_score DESC")),
        # Ranked feed of open incidents only - small and hot.
        Index(
            "ix_incidents_active_priority_score",
            text("priority_score DESC"),
            postgresql_where=text(_ACTIVE_INCIDENT_SQL),
        ),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[IncidentCategory | None] = mapped_column(
        pg_enum(IncidentCategory, "incident_category")
    )
    severity: Mapped[IncidentSeverity | None] = mapped_column(
        pg_enum(IncidentSeverity, "incident_severity")
    )
    people_affected: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    priority_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    location: Mapped[WKBElement | None] = mapped_column(geography_point())
    location_text: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[IncidentStatus] = mapped_column(
        pg_enum(IncidentStatus, "incident_status"),
        nullable=False,
        default=IncidentStatus.NEW,
        server_default=IncidentStatus.NEW.value,
    )
    report_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )

    reports: Mapped[list[IncidentReport]] = relationship(back_populates="incident")
    assignments: Mapped[list[Assignment]] = relationship(back_populates="incident")


class IncidentReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single raw report exactly as submitted. ``raw_text`` is never modified.

    ``incident_id`` is NULL until the dedup worker links the report to a canonical incident.
    ``idempotency_key`` (client-generated) makes submission and queue consumption safe to retry.
    """

    __tablename__ = "incident_reports"
    __table_args__ = (
        CheckConstraint("length(btrim(raw_text)) > 0", name="raw_text_not_blank"),
        CheckConstraint("processing_attempts >= 0", name="processing_attempts_non_negative"),
        Index("ix_incident_reports_location", "location", postgresql_using="gist"),
        Index("ix_incident_reports_incident_id", "incident_id"),
        Index("ix_incident_reports_user_id", "user_id"),
        Index("ix_incident_reports_created_at", "created_at"),
        # Lets a sweeper find stuck/failed jobs without scanning finished reports.
        Index(
            "ix_incident_reports_pending_state",
            "processing_state",
            "created_at",
            postgresql_where=text("processing_state <> 'done'"),
        ),
    )

    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[WKBElement | None] = mapped_column(geography_point())
    location_text: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    processing_state: Mapped[ReportProcessingState] = mapped_column(
        pg_enum(ReportProcessingState, "report_processing_state"),
        nullable=False,
        default=ReportProcessingState.QUEUED,
        server_default=ReportProcessingState.QUEUED.value,
    )
    processing_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    incident: Mapped[Incident | None] = relationship(back_populates="reports")
