"""Resource allocation and assignment workflow API routes (T-043, T-044).

Advisory Hungarian algorithm recommendations requiring human authority approval.
Never auto-dispatches resources.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.rbac import require_authority, require_responder
from app.modules.assignments.models import ACTIVE_ASSIGNMENT_STATUSES, Assignment, AssignmentStatus
from app.modules.audit.service import record_audit_log
from app.modules.incidents.models import ACTIVE_INCIDENT_STATUSES, Incident, IncidentStatus
from app.modules.incidents.service import extract_coordinates
from app.modules.resources.allocator import resource_allocator
from app.modules.resources.models import Resource, ResourceStatus
from app.modules.users.models import User

router = APIRouter(tags=["allocations"])


class AllocationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assignment_id: uuid.UUID | None = None
    incident_id: uuid.UUID
    incident_title: str
    incident_category: str
    priority_score: float
    resource_id: uuid.UUID
    resource_name: str
    resource_type: str
    distance_km: float
    total_cost: float
    is_compatible: bool


class AssignmentDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    resource_id: uuid.UUID
    status: AssignmentStatus
    recommended_cost: Decimal | None
    approved_by: uuid.UUID | None
    assigned_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class UpdateAssignmentStatusRequest(BaseModel):
    status: AssignmentStatus
    notes: str | None = None


@router.post(
    "/allocations/recommend",
    response_model=list[AllocationItemResponse],
    summary="Compute optimal resource allocations via Hungarian algorithm (Authority only)",
)
def generate_recommendations(
    max_distance_km: float = Query(50.0, ge=1.0, le=500.0),
    current_user: User = Depends(require_authority),
    db: Session = Depends(get_db),
) -> list[AllocationItemResponse]:
    """Run Hungarian algorithm on available resources and unassigned active incidents."""
    # 1. Fetch active incidents needing resources
    assigned_incident_ids = select(Assignment.incident_id).where(
        Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES)
    )
    incidents = (
        db.query(Incident)
        .filter(
            Incident.status.in_(ACTIVE_INCIDENT_STATUSES),
            ~Incident.id.in_(assigned_incident_ids),
        )
        .all()
    )

    # 2. Fetch available resources
    resources = db.query(Resource).filter(Resource.status == ResourceStatus.AVAILABLE).all()

    if not incidents or not resources:
        return []

    # Prepare inputs for optimizer
    inc_payloads = []
    for inc in incidents:
        lat, lon = extract_coordinates(inc.location)
        inc_payloads.append(
            {
                "id": inc.id,
                "title": inc.title,
                "category": inc.category.value if inc.category else "other",
                "severity": inc.severity.value if inc.severity else "LOW",
                "lat": lat,
                "lon": lon,
                "priority_score": float(inc.priority_score) if inc.priority_score else 50.0,
            }
        )

    res_payloads = []
    for res in resources:
        lat, lon = extract_coordinates(res.location)
        res_payloads.append(
            {
                "id": res.id,
                "name": res.name,
                "type": res.type.value if res.type else "other",
                "lat": lat,
                "lon": lon,
                "status": res.status.value,
            }
        )

    allocator = resource_allocator
    allocator.max_allowed_distance_km = max_distance_km
    raw_recs = allocator.compute_optimal_allocation(inc_payloads, res_payloads)

    results: list[AllocationItemResponse] = []
    for rec in raw_recs:
        # Create or update Assignment record in 'recommended' status
        assignment = Assignment(
            incident_id=rec.incident_id,
            resource_id=rec.resource_id,
            status=AssignmentStatus.RECOMMENDED,
            recommended_cost=Decimal(str(rec.distance_km)),
        )
        db.add(assignment)
        db.flush()

        results.append(
            AllocationItemResponse(
                assignment_id=assignment.id,
                incident_id=rec.incident_id,
                incident_title=rec.incident_title,
                incident_category=rec.incident_category,
                priority_score=rec.priority_score,
                resource_id=rec.resource_id,
                resource_name=rec.resource_name,
                resource_type=rec.resource_type,
                distance_km=rec.distance_km,
                total_cost=rec.total_cost,
                is_compatible=rec.is_compatible,
            )
        )

    db.commit()
    return results


@router.post(
    "/allocations/{assignment_id}/approve",
    response_model=AssignmentDetailResponse,
    summary="Approve recommended resource allocation (Human-in-the-loop, Authority only)",
)
def approve_allocation(
    assignment_id: uuid.UUID,
    current_user: User = Depends(require_authority),
    db: Session = Depends(get_db),
) -> AssignmentDetailResponse:
    """Approve a recommendation; updates resource and incident statuses with audit log."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment.status != AssignmentStatus.RECOMMENDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Assignment is in '{assignment.status.value}' state, cannot approve",
        )

    resource = db.query(Resource).filter(Resource.id == assignment.resource_id).first()
    incident = db.query(Incident).filter(Incident.id == assignment.incident_id).first()

    now = datetime.now(UTC)
    assignment.status = AssignmentStatus.APPROVED
    assignment.approved_by = current_user.id
    assignment.assigned_at = now

    if resource:
        resource.status = ResourceStatus.ASSIGNED
    if incident and incident.status == IncidentStatus.NEW:
        incident.status = IncidentStatus.ASSIGNED

    record_audit_log(
        db,
        actor_id=current_user.id,
        action="approve_assignment",
        entity="assignment",
        entity_id=str(assignment.id),
        payload={
            "incident_id": str(assignment.incident_id),
            "resource_id": str(assignment.resource_id),
            "cost_km": float(assignment.recommended_cost) if assignment.recommended_cost else None,
        },
    )

    db.commit()
    db.refresh(assignment)
    return AssignmentDetailResponse.model_validate(assignment)


@router.get(
    "/assignments/mine",
    response_model=list[AssignmentDetailResponse],
    summary="List active assignments for responder (Rescue/Authority)",
)
def get_my_assignments(
    current_user: User = Depends(require_responder),
    db: Session = Depends(get_db),
) -> list[AssignmentDetailResponse]:
    assignments = (
        db.query(Assignment)
        .filter(Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES))
        .order_by(Assignment.created_at.desc())
        .all()
    )
    return [AssignmentDetailResponse.model_validate(a) for a in assignments]


@router.patch(
    "/assignments/{assignment_id}/status",
    response_model=AssignmentDetailResponse,
    summary="Update assignment execution status (Rescue/Authority)",
)
def update_assignment_status(
    assignment_id: uuid.UUID,
    data: UpdateAssignmentStatusRequest,
    current_user: User = Depends(require_responder),
    db: Session = Depends(get_db),
) -> AssignmentDetailResponse:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    old_status = assignment.status
    new_status = data.status
    now = datetime.now(UTC)

    assignment.status = new_status
    if new_status == AssignmentStatus.IN_PROGRESS and not assignment.assigned_at:
        assignment.assigned_at = now
    elif new_status == AssignmentStatus.COMPLETED:
        assignment.completed_at = now
        # Free up resource
        resource = db.query(Resource).filter(Resource.id == assignment.resource_id).first()
        if resource:
            resource.status = ResourceStatus.AVAILABLE
    elif new_status == AssignmentStatus.CANCELLED:
        # Free up resource
        resource = db.query(Resource).filter(Resource.id == assignment.resource_id).first()
        if resource:
            resource.status = ResourceStatus.AVAILABLE

    record_audit_log(
        db,
        actor_id=current_user.id,
        action="update_assignment_status",
        entity="assignment",
        entity_id=str(assignment.id),
        payload={
            "from_status": old_status.value,
            "to_status": new_status.value,
            "notes": data.notes,
        },
    )

    db.commit()
    db.refresh(assignment)
    return AssignmentDetailResponse.model_validate(assignment)
