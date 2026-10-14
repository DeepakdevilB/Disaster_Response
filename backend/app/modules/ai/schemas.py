"""Schemas for AI predictions, inference results, and human overrides."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AIPredictionResponse(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    model_name: str
    model_version: str
    predicted_category: str
    category_confidence: float
    predicted_severity: str
    severity_confidence: float
    final_category: str
    final_severity: str
    extracted_entities: dict[str, Any]
    raw_output: dict[str, Any]
    override_category: str | None = None
    override_severity: str | None = None
    override_by_id: uuid.UUID | None = None
    override_reason: str | None = None
    override_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PredictionOverrideRequest(BaseModel):
    override_category: str | None = Field(
        default=None,
        examples=["medical", "rescue", "infrastructure", "fire", "flood", "other"],
    )
    override_severity: str | None = Field(
        default=None,
        examples=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    )
    reason: str = Field(
        ...,
        min_length=5,
        max_length=255,
        examples=["Field officer verified this is a chemical fire not normal smoke"],
    )


class SituationSummaryResponse(BaseModel):
    summary: str
    key_risks: list[str]
    recommended_actions: list[str]
    total_reports: int
    estimated_people_affected: int
    primary_category: str
    severity: str
    is_fallback: bool
