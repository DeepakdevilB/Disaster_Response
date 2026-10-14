"""Media attachments model for disaster incident reports."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.types import UUIDPrimaryKeyMixin


class Media(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "media"
    __table_args__ = (
        Index("ix_media_report_id", "report_id"),
        Index("ix_media_object_key", "object_key", unique=True),
    )

    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incident_reports.id", ondelete="CASCADE"),
        nullable=True,
    )
    object_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    cv_label: Mapped[str | None] = mapped_column(String(50))
    cv_score: Mapped[float | None] = mapped_column(Float)

    def __repr__(self) -> str:
        return f"<Media id={self.id} object_key={self.object_key} mime_type={self.mime_type}>"
