"""Pydantic schemas for incidents and incident reports."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.incidents.models import (
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    ReportProcessingState,
)


class CreateReportRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200, description="Short summary title")
    raw_text: str = Field(
        ..., min_length=5, max_length=5000, description="Detailed emergency description"
    )
    location_lat: float | None = Field(
        default=None, ge=-90.0, le=90.0, description="WGS84 latitude"
    )
    location_lon: float | None = Field(
        default=None, ge=-180.0, le=180.0, description="WGS84 longitude"
    )
    location_text: str | None = Field(
        default=None, max_length=255, description="Street address or landmark description"
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=64,
        description="Unique client-provided key to prevent duplicate submissions",
    )


class ReportSubmissionResponse(BaseModel):
    report_id: uuid.UUID
    incident_id: uuid.UUID | None = None
    idempotency_key: str
    processing_state: ReportProcessingState
    message: str = "Report submitted successfully and queued for processing"


class IncidentReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID | None = None
    user_id: uuid.UUID
    raw_text: str
    location_text: str | None = None
    location_lat: float | None = None
    location_lon: float | None = None
    idempotency_key: str
    processing_state: ReportProcessingState
    processing_attempts: int
    created_at: datetime


class IncidentSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    category: IncidentCategory | None = None
    severity: IncidentSeverity | None = None
    status: IncidentStatus
    priority_score: Decimal | None = None
    people_affected: int
    location_text: str | None = None
    location_lat: float | None = None
    location_lon: float | None = None
    report_count: int
    created_at: datetime
    updated_at: datetime


class IncidentDetailResponse(IncidentSummaryResponse):
    reports: list[IncidentReportResponse] = []


class UpdateIncidentStatusRequest(BaseModel):
    status: IncidentStatus = Field(..., description="Target incident status")
    notes: str | None = Field(
        default=None, max_length=500, description="Verification or resolution notes"
    )
