"""Resource-to-incident assignments (recommend -> approve -> accept -> in progress -> complete)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.types import UUIDPrimaryKeyMixin, pg_enum

if TYPE_CHECKING:
    from app.modules.incidents.models import Incident
    from app.modules.resources.models import Resource


class AssignmentStatus(enum.StrEnum):
    RECOMMENDED = "recommended"
    APPROVED = "approved"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


#: Statuses in which a resource is actually committed to an incident.
ACTIVE_ASSIGNMENT_STATUSES = (
    AssignmentStatus.APPROVED,
    AssignmentStatus.ACCEPTED,
    AssignmentStatus.IN_PROGRESS,
)


class Assignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Optimizer recommendations start as ``recommended``; only a human ``approved_by`` an
    authority commits a resource (LLM/optimizer output is advisory, never auto-dispatch)."""

    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint(
            "recommended_cost IS NULL OR recommended_cost >= 0",
            name="recommended_cost_non_negative",
        ),
        CheckConstraint(
            "completed_at IS NULL OR assigned_at IS NULL OR completed_at >= assigned_at",
            name="completed_after_assigned",
        ),
        Index("ix_assignments_incident_id", "incident_id"),
        Index("ix_assignments_resource_id", "resource_id"),
        Index("ix_assignments_status", "status"),
        # A resource can be committed to at most one incident at a time.
        Index(
            "uq_assignments_resource_active",
            "resource_id",
            unique=True,
            postgresql_where=text("status IN ('approved', 'accepted', 'in_progress')"),
        ),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=False
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        pg_enum(AssignmentStatus, "assignment_status"),
        nullable=False,
        default=AssignmentStatus.RECOMMENDED,
        server_default=AssignmentStatus.RECOMMENDED.value,
    )
    recommended_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    incident: Mapped[Incident] = relationship(back_populates="assignments")
    resource: Mapped[Resource] = relationship()
