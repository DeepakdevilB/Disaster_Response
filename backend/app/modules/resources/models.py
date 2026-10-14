"""Deployable resources: ambulances, boats, rescue teams, kits."""

from __future__ import annotations

import enum

from geoalchemy2 import WKBElement
from sqlalchemy import CheckConstraint, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.types import UUIDPrimaryKeyMixin, geography_point, pg_enum


class ResourceType(enum.StrEnum):
    AMBULANCE = "ambulance"
    RESCUE_TEAM = "rescue_team"
    BOAT = "boat"
    MEDICAL_KIT = "medical_kit"
    FOOD_KIT = "food_kit"
    OTHER = "other"


class ResourceStatus(enum.StrEnum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    OFFLINE = "offline"


class Resource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint("capacity >= 1", name="capacity_positive"),
        Index("ix_resources_location", "location", postgresql_using="gist"),
        # Allocator query: "available boats" etc.
        Index("ix_resources_type_status", "type", "status"),
    )

    type: Mapped[ResourceType] = mapped_column(
        pg_enum(ResourceType, "resource_type"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[ResourceStatus] = mapped_column(
        pg_enum(ResourceStatus, "resource_status"),
        nullable=False,
        default=ResourceStatus.AVAILABLE,
        server_default=ResourceStatus.AVAILABLE.value,
    )
    location: Mapped[WKBElement | None] = mapped_column(geography_point())
    capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
