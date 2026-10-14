"""ORM model for AI predictions and authority overrides (T-035)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin
from app.db.types import UUIDPrimaryKeyMixin


class AIPrediction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_predictions"
    __table_args__ = (
        Index("ix_ai_predictions_report_id", "report_id"),
        Index("ix_ai_predictions_model", "model_name", "model_version"),
        Index("ix_ai_predictions_predicted_category", "predicted_category"),
        Index("ix_ai_predictions_predicted_severity", "predicted_severity"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incident_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    predicted_category: Mapped[str] = mapped_column(String(50), nullable=False)
    category_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_severity: Mapped[str] = mapped_column(String(50), nullable=False)
    severity_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Structured entities: people count, location, resources
    extracted_entities: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    # Full probability distributions and debug payloads
    raw_output: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    # Authority human-in-the-loop override fields
    override_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    override_severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    override_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    override_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    override_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def final_category(self) -> str:
        """Effective category (manual override takes precedence over AI prediction)."""
        return self.override_category or self.predicted_category

    @property
    def final_severity(self) -> str:
        """Effective severity (manual override takes precedence over AI prediction)."""
        return self.override_severity or self.predicted_severity

    def __repr__(self) -> str:
        return (
            f"<AIPrediction id={self.id} report_id={self.report_id} "
            f"category={self.final_category} severity={self.final_severity}>"
        )
