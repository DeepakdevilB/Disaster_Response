"""Pydantic schemas for resources management."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.resources.models import ResourceStatus, ResourceType


class ResourceBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Ambulance-BLR-01"])
    type: ResourceType = Field(..., examples=[ResourceType.AMBULANCE])
    capacity: int = Field(default=1, ge=1, description="Capacity, must be positive integer")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    type: ResourceType | None = None
    status: ResourceStatus | None = None
    capacity: int | None = Field(default=None, ge=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class ResourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: ResourceType
    status: ResourceStatus
    capacity: int
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
