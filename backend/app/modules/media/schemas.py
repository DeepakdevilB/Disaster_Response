"""Schemas for media upload and retrieval."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UploadUrlRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255, examples=["damage.jpg"])
    mime_type: str = Field(..., examples=["image/jpeg", "image/png", "image/webp"])
    file_size: int = Field(..., gt=0, le=10 * 1024 * 1024, description="Size in bytes (max 10MB)")
    report_id: uuid.UUID | None = Field(default=None, description="Optional incident report id")


class UploadUrlResponse(BaseModel):
    upload_url: str
    method: str
    object_key: str
    content_type: str


class MediaResponse(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID | None
    object_key: str
    mime_type: str
    file_size: int
    download_url: str
    cv_label: str | None = None
    cv_score: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
