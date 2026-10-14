"""API endpoints for resource and rescue-team management (T-021)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.rbac import require_roles
from app.modules.audit.service import record_audit_log
from app.modules.incidents.service import extract_coordinates
from app.modules.resources.models import Resource, ResourceStatus, ResourceType
from app.modules.resources.schemas import ResourceCreate, ResourceResponse, ResourceUpdate
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/resources", tags=["resources"])


def _to_resource_response(res: Resource) -> ResourceResponse:
    lat, lon = extract_coordinates(res.location)
    return ResourceResponse(
        id=res.id,
        name=res.name,
        type=res.type,
        status=res.status,
        capacity=res.capacity,
        latitude=lat,
        longitude=lon,
        created_at=res.created_at,
        updated_at=res.updated_at,
    )


def _to_point_geom(db: Session, lat: float | None, lon: float | None):
    if lat is None or lon is None:
        return None
    wkt = f"POINT({lon} {lat})"
    if db.bind is not None and db.bind.dialect.name == "sqlite":
        return wkt
    return WKTElement(wkt, srid=4326)


@router.get(
    "",
    response_model=list[ResourceResponse],
    summary="List resources with optional filtering by type and status",
)
def list_resources(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_roles(UserRole.AUTHORITY, UserRole.ADMIN, UserRole.RESCUE))
    ],
    type: ResourceType | None = Query(None, description="Filter by resource type"),
    status: ResourceStatus | None = Query(None, description="Filter by availability status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[ResourceResponse]:
    stmt = select(Resource)
    if type is not None:
        stmt = stmt.where(Resource.type == type)
    if status is not None:
        stmt = stmt.where(Resource.status == status)
    stmt = stmt.order_by(Resource.created_at.desc()).offset(skip).limit(limit)
    rows = db.scalars(stmt).all()
    return [_to_resource_response(r) for r in rows]


@router.post(
    "",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new deployable resource (authority/admin only)",
)
def create_resource(
    payload: ResourceCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.AUTHORITY, UserRole.ADMIN))],
) -> ResourceResponse:
    existing = db.scalar(select(Resource).where(Resource.name == payload.name))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Resource with name '{payload.name}' already exists",
        )

    geom = _to_point_geom(db, payload.latitude, payload.longitude)
    resource = Resource(
        name=payload.name,
        type=payload.type,
        capacity=payload.capacity,
        location=geom,
        status=ResourceStatus.AVAILABLE,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)

    record_audit_log(
        db=db,
        actor_id=current_user.id,
        action="resource.create",
        entity="resource",
        entity_id=resource.id,
        payload={"name": resource.name, "type": resource.type.value, "capacity": resource.capacity},
    )

    return _to_resource_response(resource)


@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Retrieve resource detail",
)
def get_resource(
    resource_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_roles(UserRole.AUTHORITY, UserRole.ADMIN, UserRole.RESCUE))
    ],
) -> ResourceResponse:
    resource = db.scalar(select(Resource).where(Resource.id == resource_id))
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return _to_resource_response(resource)


@router.patch(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Update resource status, location, or capacity",
)
def update_resource(
    resource_id: uuid.UUID,
    payload: ResourceUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_roles(UserRole.AUTHORITY, UserRole.ADMIN, UserRole.RESCUE))
    ],
) -> ResourceResponse:
    resource = db.scalar(select(Resource).where(Resource.id == resource_id))
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    changes: dict[str, str | int] = {}
    if payload.name is not None and payload.name != resource.name:
        existing = db.scalar(select(Resource).where(Resource.name == payload.name))
        if existing and existing.id != resource.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Resource name already taken"
            )
        resource.name = payload.name
        changes["name"] = payload.name
    if payload.type is not None:
        resource.type = payload.type
        changes["type"] = payload.type.value
    if payload.status is not None:
        resource.status = payload.status
        changes["status"] = payload.status.value
    if payload.capacity is not None:
        resource.capacity = payload.capacity
        changes["capacity"] = payload.capacity
    if payload.latitude is not None or payload.longitude is not None:
        lat = (
            payload.latitude
            if payload.latitude is not None
            else extract_coordinates(resource.location)[0]
        )
        lon = (
            payload.longitude
            if payload.longitude is not None
            else extract_coordinates(resource.location)[1]
        )
        resource.location = _to_point_geom(db, lat, lon)
        changes["location"] = f"{lat},{lon}"

    db.commit()
    db.refresh(resource)

    record_audit_log(
        db=db,
        actor_id=current_user.id,
        action="resource.update",
        entity="resource",
        entity_id=resource.id,
        payload=changes,
    )

    return _to_resource_response(resource)
